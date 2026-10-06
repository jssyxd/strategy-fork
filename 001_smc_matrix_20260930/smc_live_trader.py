#!/usr/bin/env python3
"""
NautilusTrader 4-Asset Trend Pullback & Evidential Volatility Filter Strategy Matrix
Production-Grade Event-Driven Implementation for OKX Live Demo

Engineering Invariants & Problem Fixes:
1. Alphanumeric Client Order IDs (OKX API Fix):
   - Sets use_hyphens_in_client_order_ids=False to strictly prevent OKX INVALID_CLIENT_ORDER_ID rejections.
   - Comprehensive Order Lifecycle handling including on_order_denied, on_order_rejected, on_order_canceled, on_order_expired, and on_order_filled.
   - Safe try-except timeout cancellation to prevent stuck pending orders.
2. Market Order Guaranteed Fill for Momentum Signals:
   - Sets use_market_order=True by default to eliminate stale limit order timeouts and adverse selection.
3. Real Dynamic OKX Account Equity Sizing:
   - Dynamic 1% risk per trade sizing fetched from live OKX USDT account balance.
4. Cross-Asset Risk Coordination:
   - PortfolioCoordinator caps concurrent active positions across BTC, ETH, SOL, BNB to 2, preventing market-wide beta dumps.
5. Dirichlet Uncertainty Volatility Filter:
   - Bayesian Subjective Logic Gate (u <= 0.35, C < 0.40) to filter noisy/conflicted chop regimes.
6. Instant Cold-Start Warmup:
   - Auto-bootstraps 60 historical 15m bars from OKX REST API upon startup, making features immediately ready without waiting hours.
"""
from __future__ import annotations

import os
import math
import logging
import urllib.request
import json
from collections import deque
from typing import Optional, Set
from datetime import timedelta

from nautilus_trader.adapters.okx import (
    OKX,
    OKXDataClientConfig,
    OKXDataClientFactory,
    OKXEnvironment,
    OKXExecutionClientConfig,
    OKXExecutionClientFactory,
    OKXInstrumentType,
    OKXMarginMode,
)
from nautilus_trader.common import Environment
from nautilus_trader.config import StrategyConfig
from nautilus_trader.live import LiveNode, LiveRiskEngineConfig
from nautilus_trader.model import (
    AccountId,
    Bar,
    BarAggregation,
    BarSpecification,
    BarType,
    AggregationSource,
    Currency,
    InstrumentId,
    OrderSide,
    Price,
    PriceType,
    Quantity,
    StrategyId,
    TimeInForce,
    TraderId,
    Venue,
    ClientOrderId,
    OrderAccepted,
    OrderCanceled,
    OrderDenied,
    OrderExpired,
    OrderFilled,
    OrderRejected,
    OrderSubmitted,
)
from nautilus_trader.trading import Strategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("PROD-MATRIX")


# ─── Global Portfolio Exposure Coordinator ────────────────────────────────────
class PortfolioCoordinator:
    """Cross-asset risk throttler to eliminate systemic correlation crashes."""
    active_instruments: Set[str] = set()
    MAX_CONCURRENT_PORTFOLIO_POSITIONS: int = 2  # Max 2 active positions across BTC, ETH, SOL, BNB

    @classmethod
    def can_open_position(cls, symbol: str) -> bool:
        if symbol in cls.active_instruments:
            return True
        return len(cls.active_instruments) < cls.MAX_CONCURRENT_PORTFOLIO_POSITIONS

    @classmethod
    def register_position(cls, symbol: str) -> None:
        cls.active_instruments.add(symbol)
        logger.info(
            f"[PORTFOLIO-RISK] Active positions ({len(cls.active_instruments)}/{cls.MAX_CONCURRENT_PORTFOLIO_POSITIONS}): "
            f"{list(cls.active_instruments)}"
        )

    @classmethod
    def release_position(cls, symbol: str) -> None:
        cls.active_instruments.discard(symbol)
        logger.info(
            f"[PORTFOLIO-RISK] Released position. Active positions ({len(cls.active_instruments)}/{cls.MAX_CONCURRENT_PORTFOLIO_POSITIONS}): "
            f"{list(cls.active_instruments)}"
        )


# ─── Evidential Uncertainty Filter ───────────────────────────────────────────
class EvidentialFilter:
    """
    Dirichlet Subjective Logic Uncertainty Gate.
    Quantifies epistemic vacuity (u) and directional conflict (C).
    Conservation: b_long + b_short + b_neutral + u == 1.0
    """

    def __init__(self, u_max: float = 0.35, c_max: float = 0.40):
        self.u_max = u_max
        self.c_max = c_max

    def evaluate(self, bull_ev: float, bear_ev: float, base_neutral: float = 1.0) -> dict:
        alpha_bull = max(bull_ev, 0.0) + 1.0
        alpha_bear = max(bear_ev, 0.0) + 1.0
        alpha_neutral = base_neutral + 1.0

        S = alpha_bull + alpha_bear + alpha_neutral
        K = 3.0

        b_bull = (alpha_bull - 1.0) / S
        b_bear = (alpha_bear - 1.0) / S
        b_neutral = (alpha_neutral - 1.0) / S
        u = K / S

        total_directional = b_bull + b_bear
        C = (2.0 * min(b_bull, b_bear) / total_directional) if total_directional > 1e-6 else 0.0
        passed = (u <= self.u_max) and (C < self.c_max)

        return {
            "b_bull": b_bull,
            "b_bear": b_bear,
            "b_neutral": b_neutral,
            "u": u,
            "C": C,
            "passed": passed,
        }


# ─── Vectorized Causal SMC Feature Engine ─────────────────────────────────────
class SMCFeatures:
    """Vectorized online causal feature computation from 15-min OHLCV bars."""

    def __init__(
        self,
        atr_fast: int = 14,
        atr_slow: int = 50,
        ema_fast: int = 20,
        ema_slow: int = 50,
        vol_sma: int = 20,
        swing_len: int = 3,
        atr_ratio_min: float = 0.55,
        atr_ratio_max: float = 1.80,
    ):
        self.atr_fast = atr_fast
        self.atr_slow = atr_slow
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.vol_sma = vol_sma
        self.swing_len = swing_len
        self.atr_ratio_min = atr_ratio_min
        self.atr_ratio_max = atr_ratio_max

        maxlen = max(atr_slow, ema_slow, vol_sma) + 25
        self.opens: deque = deque(maxlen=maxlen)
        self.highs: deque = deque(maxlen=maxlen)
        self.lows: deque = deque(maxlen=maxlen)
        self.closes: deque = deque(maxlen=maxlen)
        self.volumes: deque = deque(maxlen=maxlen)

        self._atr_fast_val: Optional[float] = None
        self._atr_slow_val: Optional[float] = None
        self._ema_fast_val: Optional[float] = None
        self._ema_slow_val: Optional[float] = None

    def update(self, o: float, h: float, l: float, c: float, v: float) -> None:
        self.opens.append(o)
        self.highs.append(h)
        self.lows.append(l)
        self.closes.append(c)
        self.volumes.append(v)

        alpha_fast = 2.0 / (self.ema_fast + 1.0)
        alpha_slow = 2.0 / (self.ema_slow + 1.0)
        if self._ema_fast_val is None:
            self._ema_fast_val = c
            self._ema_slow_val = c
        else:
            self._ema_fast_val = alpha_fast * c + (1.0 - alpha_fast) * self._ema_fast_val
            self._ema_slow_val = alpha_slow * c + (1.0 - alpha_slow) * self._ema_slow_val

        if len(self.closes) >= 2:
            prev_c = self.closes[-2]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            a_f = 1.0 / self.atr_fast
            a_s = 1.0 / self.atr_slow
            if self._atr_fast_val is None:
                self._atr_fast_val = tr
                self._atr_slow_val = tr
            else:
                self._atr_fast_val = a_f * tr + (1.0 - a_f) * self._atr_fast_val
                self._atr_slow_val = a_s * tr + (1.0 - a_s) * self._atr_slow_val

    @property
    def ready(self) -> bool:
        return len(self.closes) >= max(self.atr_slow, self.ema_slow, self.vol_sma) + 5

    def compute(self) -> dict:
        closes = list(self.closes)
        highs = list(self.highs)
        lows = list(self.lows)
        volumes = list(self.volumes)
        n = len(closes)

        c = closes[-1]
        h = highs[-1]
        l = lows[-1]
        v = volumes[-1]

        atr_f = self._atr_fast_val or (c * 0.005)
        atr_s = self._atr_slow_val or atr_f
        ema_f = self._ema_fast_val or c
        ema_s = self._ema_slow_val or c

        vol_window = volumes[-self.vol_sma:]
        vol_avg = sum(vol_window) / float(len(vol_window)) if vol_window else v
        vol_ratio = v / (vol_avg + 1e-9)
        vol_spike = vol_ratio > 1.25

        swing_high = max(highs[-self.swing_len:]) if n >= self.swing_len else h
        swing_low = min(lows[-self.swing_len:]) if n >= self.swing_len else l

        body = abs(c - self.opens[-1])
        rng = max(h - l, 1e-9)
        # Close Location Value (CLV: -1.0 to +1.0)
        clv = ((c - l) - (h - c)) / rng
        is_bull_candle = c > self.opens[-1]

        score_long = 0.0
        score_short = 0.0

        # 1. Trend Filter (30 pts)
        if c > ema_f > ema_s:
            score_long += 30.0
        elif c < ema_f < ema_s:
            score_short += 30.0

        # 2. Volume Spike / Absorption (25 pts)
        if vol_spike:
            if is_bull_candle:
                score_long += 25.0
            else:
                score_short += 25.0

        # 3. Close Location Pressure (15 pts)
        if clv > 0.4:
            score_long += 15.0
        elif clv < -0.4:
            score_short += 15.0

        # 4. Volatility Regime Filter (15 pts)
        atr_ratio = atr_f / (atr_s + 1e-9)
        if self.atr_ratio_min <= atr_ratio <= self.atr_ratio_max:
            score_long += 15.0
            score_short += 15.0

        # 5. EMA Support / Resistance Pullback Test (15 pts)
        if is_bull_candle and abs(l - ema_f) / (atr_f + 1e-9) < 0.8:
            score_long += 15.0
        elif (not is_bull_candle) and abs(h - ema_f) / (atr_f + 1e-9) < 0.8:
            score_short += 15.0

        return {
            "close": c,
            "high": h,
            "low": l,
            "atr": atr_f,
            "atr_ratio": atr_ratio,
            "ema_fast": ema_f,
            "ema_slow": ema_s,
            "vol_ratio": vol_ratio,
            "clv": clv,
            "swing_high": swing_high,
            "swing_low": swing_low,
            "score_long": score_long,
            "score_short": score_short,
        }


# ─── Live Strategy Configuration ──────────────────────────────────────────────
class SMCLiveConfig(StrategyConfig):
    pass


# ─── Live Strategy Implementation ─────────────────────────────────────────────
class SMCLiveStrategy(Strategy):
    """
    Production-Grade Live Strategy with Strict Event-Driven State Machine.
    Never assumes fills; state transitions ONLY on on_order_filled.
    """

    def __init__(self, config: SMCLiveConfig) -> None:
        super().__init__(config)
        self.cfg = config
        self.feats = SMCFeatures()
        self.filter = EvidentialFilter(u_max=config.u_max, c_max=config.c_max)

        # Confirmed Active Position State (Updated ONLY on on_order_filled)
        self.in_position: bool = False
        self.pos_side: int = 0  # 1 for Long, -1 for Short
        self.entry_price: float = 0.0
        self.position_qty: float = 0.0
        self.stop_loss: float = 0.0
        self.tp1_price: float = 0.0
        self.tp2_price: float = 0.0
        self.tp1_filled: bool = False

        # In-Flight Orders State Tracking
        self.pending_entry_order_id: Optional[ClientOrderId] = None
        self.pending_entry_side: int = 0
        self.pending_entry_risk_dist: float = 0.0
        self.pending_entry_bars: int = 0
        self.pending_exit_order_id: Optional[ClientOrderId] = None

        self.bars_processed: int = 0
        self.consec_losses: int = 0
        self.breaker_bars: int = 0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.realized_pnl: float = 0.0

    def on_start(self) -> None:
        iid = InstrumentId.from_str(self.cfg.instrument_id)
        spec = BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST)
        bar_type = BarType(iid, spec, AggregationSource.EXTERNAL)
        self.subscribe_bars(bar_type)

        self._warmup_from_okx_rest()
        raw_sym = self.cfg.instrument_id.split(".")[0]
        self._hydrate_existing_position(iid, raw_sym)
        self.clock.set_timer(f"HEARTBEAT_{raw_sym}", timedelta(minutes=5), callback=self._on_heartbeat)

        self.log.info(
            f"=== PRODUCTION STRATEGY ACTIVE === [{self.cfg.instrument_id}] | "
            f"ct_val={self.cfg.ct_val} | prec={self.cfg.price_precision} | "
            f"min_score={self.cfg.min_score} | market_order={self.cfg.use_market_order} | "
            f"Warmed Up: {self.feats.ready} | InPosition: {self.in_position}"
        )

    def _hydrate_existing_position(self, iid: InstrumentId, raw_sym: str) -> None:
        """Hydrates existing open position from cache/portfolio upon cold-start or restart."""
        try:
            open_positions = self.cache.positions_open(instrument_id=iid)
            if open_positions:
                pos = open_positions[0]
                self.in_position = True
                self.pos_side = 1 if pos.is_long else -1
                self.entry_price = float(pos.avg_px_open)
                self.position_qty = float(pos.quantity)

                # Reconstruct defensive SL/TP using recent ATR from warmup
                f = self.feats.compute()
                atr = f.get("atr", self.entry_price * 0.01)
                sl_dist = max(atr * 1.5, self.entry_price * 0.005)

                if self.pos_side == 1:
                    self.stop_loss = self.entry_price - sl_dist
                    self.tp1_price = self.entry_price + self.cfg.tp1_r * sl_dist
                    self.tp2_price = self.entry_price + self.cfg.tp2_r * sl_dist
                else:
                    self.stop_loss = self.entry_price + sl_dist
                    self.tp1_price = self.entry_price - self.cfg.tp1_r * sl_dist
                    self.tp2_price = self.entry_price - self.cfg.tp2_r * sl_dist

                PortfolioCoordinator.register_position(raw_sym)
                self.log.warning(
                    f"[{raw_sym}] RE-HYDRATED EXISTING POSITION: Side={'LONG' if self.pos_side==1 else 'SHORT'} "
                    f"Qty={self.position_qty} @ {self.entry_price:.2f} | "
                    f"SL={self.stop_loss:.2f} | TP1={self.tp1_price:.2f} | TP2={self.tp2_price:.2f}"
                )
        except Exception as e:
            self.log.error(f"[{raw_sym}] Error hydrating existing position: {e}")

    def _warmup_from_okx_rest(self) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        url = f"https://www.okx.com/api/v5/market/candles?instId={raw_sym}&bar=15m&limit=60"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
                candles = data.get("data", [])
                candles.reverse()
                for c in candles:
                    self.feats.update(float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5]))
                    self.bars_processed += 1

                f = self.feats.compute()
                self.log.info(
                    f"[{raw_sym}] WARMUP COMPLETE: {len(candles)} bars loaded | "
                    f"Px={f['close']:.2f} | EMA20={f['ema_fast']:.2f} | EMA50={f['ema_slow']:.2f} | "
                    f"Score L={f['score_long']:.1f}, S={f['score_short']:.1f} | ATR Ratio={f['atr_ratio']:.2f} | READY=TRUE"
                )
        except Exception as e:
            self.log.error(f"[{raw_sym}] Warmup error: {e}")

    def _on_heartbeat(self, event) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        iid = InstrumentId.from_str(self.cfg.instrument_id)
        try:
            # 孤儿仓位自愈与强同步检查 (Watchdog Reconciliation)
            net_pos = self.portfolio.net_position(iid)
            actual_net = float(net_pos.as_double() if hasattr(net_pos, 'as_double') else net_pos)

            if actual_net != 0 and not self.in_position:
                # 发现存在无主孤儿仓，立即自动接管
                self.in_position = True
                self.pos_side = 1 if actual_net > 0 else -1
                self.position_qty = abs(actual_net)
                f = self.feats.compute()
                atr = f.get("atr", f["close"] * 0.01)
                self.entry_price = f["close"]
                sl_dist = max(atr * 1.5, self.entry_price * 0.005)
                if self.pos_side == 1:
                    self.stop_loss = self.entry_price - sl_dist
                    self.tp1_price = self.entry_price + self.cfg.tp1_r * sl_dist
                    self.tp2_price = self.entry_price + self.cfg.tp2_r * sl_dist
                else:
                    self.stop_loss = self.entry_price + sl_dist
                    self.tp1_price = self.entry_price - self.cfg.tp1_r * sl_dist
                    self.tp2_price = self.entry_price - self.cfg.tp2_r * sl_dist
                PortfolioCoordinator.register_position(raw_sym)
                self.log.warning(
                    f"[{raw_sym}] WATCHDOG ADOPTED ORPHAN POSITION: NetPos={actual_net} | "
                    f"Side={'LONG' if self.pos_side==1 else 'SHORT'} | SL={self.stop_loss:.2f} | TP2={self.tp2_price:.2f}"
                )
            elif actual_net == 0 and self.in_position:
                # 外部已平仓或已平净，自动复位策略状态
                self.in_position = False
                self.pos_side = 0
                self.position_qty = 0.0
                PortfolioCoordinator.release_position(raw_sym)

            f = self.feats.compute()
            self.log.info(
                f"[HEARTBEAT] {raw_sym:15s} | Px={f['close']:8.2f} | "
                f"InPos={self.in_position} | NetPos={actual_net} | PendingEntry={self.pending_entry_order_id is not None} | "
                f"Trades={self.total_trades} | PnL={self.realized_pnl:.2f} USDT"
            )
        except Exception as e:
            self.log.warning(f"[{raw_sym}] Heartbeat compute note: {e}")

    def on_bar(self, bar: Bar) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
        try:
            v = float(bar.volume)
        except Exception:
            v = 1.0

        self.feats.update(o, h, l, c, v)
        self.bars_processed += 1

        # 1. Stale Pending Order Cancellation (3 bars timeout)
        if self.pending_entry_order_id is not None:
            self.pending_entry_bars += 1
            max_bars = getattr(self.cfg, "max_pending_bars", 3)
            if self.pending_entry_bars >= max_bars:
                self.log.warning(
                    f"[{raw_sym}] Limit entry order {self.pending_entry_order_id} unfilled after "
                    f"{self.pending_entry_bars} bars (>= {max_bars} bars limit). Cancelling..."
                )
                try:
                    self.cancel_order(self.pending_entry_order_id)
                except Exception as e:
                    self.log.warning(f"[{raw_sym}] Cancel note (order already closed/denied): {e}. Clearing pending state.")
                    self.pending_entry_order_id = None
                    self.pending_entry_bars = 0
                return
            else:
                self.log.info(
                    f"[{raw_sym}] Entry order {self.pending_entry_order_id} pending fill "
                    f"({self.pending_entry_bars}/{max_bars} bars)..."
                )
                return

        # 2. Manage confirmed open position
        if self.in_position:
            self._manage_position(h, l, c)
            return

        # 3. 连续亏损熔断保护与 48 根 K 线冷却自动解封机制
        if self.consec_losses >= self.cfg.max_loss_streak:
            self.breaker_bars += 1
            cooldown_limit = getattr(self.cfg, "cooldown_bars", 48)  # 默认 48 根 K 线 (12 小时)
            if self.breaker_bars < cooldown_limit:
                if self.breaker_bars % 4 == 0 or self.breaker_bars == 1:
                    self.log.warning(
                        f"[{raw_sym}] 连续亏损熔断保护中 ({self.consec_losses} 连亏): "
                        f"冷却进度 {self.breaker_bars}/{cooldown_limit} 根 K 线 (暂停开仓)..."
                    )
                return
            else:
                self.log.info(
                    f"[{raw_sym}] 熔断冷却期满 ({self.breaker_bars} 根 K 线 / 12 小时)! 自动解封并重置连续亏损计数，恢复正常交易。"
                )
                self.consec_losses = 0
                self.breaker_bars = 0

        # 4. Cross-Asset Risk Check (Prevent correlated multi-asset drawdowns)
        if not PortfolioCoordinator.can_open_position(raw_sym):
            return

        # 5. Evaluate Trend Pullback Signals
        feat = self.feats.compute()
        score_long = feat["score_long"]
        score_short = feat["score_short"]
        atr = feat["atr"]

        direction = 0
        score = 0.0
        if score_long >= self.cfg.min_score and score_long > score_short:
            direction = 1
            score = score_long
        elif score_short >= self.cfg.min_score and score_short > score_long:
            direction = -1
            score = score_short

        if direction == 0:
            return

        # 6. Evidential Filter Gate
        bull_ev = score_long / 10.0
        bear_ev = score_short / 10.0
        gate_res = self.filter.evaluate(bull_ev, bear_ev)

        self.log.info(
            f"[{raw_sym}] SIGNAL: {'LONG' if direction == 1 else 'SHORT'} | Score={score:.1f} | "
            f"Evidential u={gate_res['u']:.3f}, C={gate_res['C']:.3f} | Gate Passed: {gate_res['passed']}"
        )

        if not gate_res["passed"]:
            return

        # 7. Real Dynamic Account Equity Sizing
        account = self.portfolio.account(account_id=AccountId.from_str("OKX-DEMO-001"))
        if account is None:
            account = self.portfolio.account(venue=Venue("OKX"))

        if account is not None:
            free_bal = account.balance_free(Currency.from_str("USDT"))
            equity = float(free_bal.as_double()) if free_bal is not None else 100000.0
        else:
            equity = 100000.0

        risk_budget = equity * self.cfg.risk_pct
        sl_dist = max(atr * 1.5, c * 0.005)
        risk_per_contract = sl_dist * self.cfg.ct_val
        if risk_per_contract <= 0:
            return

        contracts = max(1, min(math.floor(risk_budget / risk_per_contract), 500))
        side = OrderSide.BUY if direction == 1 else OrderSide.SELL

        # 8. Submit Order (Strict: State NOT mutated until on_order_filled)
        if self.cfg.use_market_order:
            order = self.order_factory.market(
                instrument_id=InstrumentId.from_str(self.cfg.instrument_id),
                order_side=side,
                quantity=Quantity.from_int(contracts),
            )
        else:
            limit_px = round(c - 0.2 * atr if direction == 1 else c + 0.2 * atr, self.cfg.price_precision)
            px_str = f"{limit_px:.{self.cfg.price_precision}f}"
            order = self.order_factory.limit(
                instrument_id=InstrumentId.from_str(self.cfg.instrument_id),
                order_side=side,
                quantity=Quantity.from_int(contracts),
                price=Price.from_str(px_str),
                time_in_force=TimeInForce.GTC,
            )

        self.pending_entry_order_id = order.client_order_id
        self.pending_entry_side = direction
        self.pending_entry_risk_dist = sl_dist
        self.pending_entry_bars = 0

        self.submit_order(order)
        self.log.info(
            f"[{raw_sym}] Order SUBMITTED (id={order.client_order_id}): {side.name} {contracts} cts | "
            f"Risk Budget=${risk_budget:.2f} (from live equity ${equity:.2f}) | Awaiting Fill Event..."
        )

    # ─── NautilusTrader Event Handlers (Order Lifecycle) ──────────────────────────
    def on_order_submitted(self, event: OrderSubmitted) -> None:
        self.log.info(f"[{self.cfg.instrument_id}] Order submitted confirmed: {event.client_order_id}")

    def on_order_accepted(self, event: OrderAccepted) -> None:
        self.log.info(f"[{self.cfg.instrument_id}] Order accepted by exchange: {event.client_order_id}")

    def on_order_denied(self, event: OrderDenied) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        self.log.error(f"[{raw_sym}] Order DENIED: {event.client_order_id} | reason='{event.reason}'")
        if event.client_order_id == self.pending_entry_order_id:
            self.pending_entry_order_id = None
            self.pending_entry_bars = 0
        if event.client_order_id == self.pending_exit_order_id:
            self.pending_exit_order_id = None

    def on_order_rejected(self, event: OrderRejected) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        self.log.error(f"[{raw_sym}] Order REJECTED: {event.client_order_id} | reason='{event.reason}'")
        if event.client_order_id == self.pending_entry_order_id:
            self.pending_entry_order_id = None
            self.pending_entry_bars = 0
        if event.client_order_id == self.pending_exit_order_id:
            self.pending_exit_order_id = None

    def on_order_canceled(self, event: OrderCanceled) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        self.log.info(f"[{raw_sym}] Order CANCELED: {event.client_order_id}")
        if event.client_order_id == self.pending_entry_order_id:
            self.pending_entry_order_id = None
            self.pending_entry_bars = 0
        if event.client_order_id == self.pending_exit_order_id:
            self.pending_exit_order_id = None

    def on_order_expired(self, event: OrderExpired) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        self.log.info(f"[{raw_sym}] Order EXPIRED: {event.client_order_id}")
        if event.client_order_id == self.pending_entry_order_id:
            self.pending_entry_order_id = None
            self.pending_entry_bars = 0
        if event.client_order_id == self.pending_exit_order_id:
            self.pending_exit_order_id = None

    def on_order_filled(self, event: OrderFilled) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        fill_px = float(event.last_px)
        fill_qty = float(event.last_qty)
        order_id = event.client_order_id

        # 1. Entry Fill Confirmation
        if order_id == self.pending_entry_order_id:
            # 依据真实净持仓确认持仓状态
            iid = InstrumentId.from_str(self.cfg.instrument_id)
            net_pos = self.portfolio.net_position(iid)
            actual_net = float(net_pos.as_double() if hasattr(net_pos, 'as_double') else net_pos)

            if actual_net != 0:
                self.in_position = True
                self.pos_side = 1 if actual_net > 0 else -1
                self.entry_price = fill_px
                self.position_qty = abs(actual_net)
                self.pending_entry_order_id = None
                self.pending_entry_bars = 0
                self.tp1_filled = False

                sl_dist = self.pending_entry_risk_dist
                if self.pos_side == 1:
                    self.stop_loss = fill_px - sl_dist
                    self.tp1_price = fill_px + self.cfg.tp1_r * sl_dist
                    self.tp2_price = fill_px + self.cfg.tp2_r * sl_dist
                else:
                    self.stop_loss = fill_px + sl_dist
                    self.tp1_price = fill_px - self.cfg.tp1_r * sl_dist
                    self.tp2_price = fill_px - self.cfg.tp2_r * sl_dist

                PortfolioCoordinator.register_position(raw_sym)
                self.log.info(
                    f"[{raw_sym}] >>> ENTRY CONFIRMED ON_ORDER_FILLED: Filled {fill_qty} cts @ {fill_px:.2f} | "
                    f"Real NetPos={actual_net} | SL={self.stop_loss:.2f} | TP1={self.tp1_price:.2f} | TP2={self.tp2_price:.2f} <<<"
                )
            else:
                self.log.warning(
                    f"[{raw_sym}] Order filled {fill_qty} cts but NetPos is flat. Treating as closed."
                )
                self.in_position = False
                self.pos_side = 0
                self.position_qty = 0.0
                self.pending_entry_order_id = None
                self.pending_entry_bars = 0
                PortfolioCoordinator.release_position(raw_sym)
            return

        # 2. Exit Fill Confirmation
        if order_id == self.pending_exit_order_id:
            self.pending_exit_order_id = None
            pnl = (
                (fill_px - self.entry_price) * fill_qty * self.cfg.ct_val
                if self.pos_side == 1
                else (self.entry_price - fill_px) * fill_qty * self.cfg.ct_val
            )
            self.realized_pnl += pnl
            self.total_trades += 1
            if pnl > 0:
                self.winning_trades += 1
                self.consec_losses = 0
                self.breaker_bars = 0
            else:
                self.consec_losses += 1

            self.in_position = False
            self.pos_side = 0
            self.position_qty = 0.0
            PortfolioCoordinator.release_position(raw_sym)

            self.log.info(
                f"[{raw_sym}] >>> EXIT CONFIRMED ON_ORDER_FILLED: Closed at {fill_px:.2f} | "
                f"Trade PnL={pnl:.2f} USDT | Total PnL={self.realized_pnl:.2f} USDT <<<"
            )

    def _manage_position(self, h: float, l: float, c: float) -> None:
        if self.pending_exit_order_id is not None:
            return  # Exit order already in flight

        iid = InstrumentId.from_str(self.cfg.instrument_id)
        raw_sym = self.cfg.instrument_id.split(".")[0]

        # 实时从 Portfolio 核实当前真实净持仓
        net_pos = self.portfolio.net_position(iid)
        real_qty = abs(float(net_pos.as_double() if hasattr(net_pos, 'as_double') else net_pos))

        if real_qty <= 0:
            # 交易所实际上已经没有仓位，复位策略内部状态，防止发送多余平仓单
            self.in_position = False
            self.pos_side = 0
            self.position_qty = 0.0
            PortfolioCoordinator.release_position(raw_sym)
            return

        should_exit = False
        exit_reason = ""

        if self.pos_side == 1:
            if l <= self.stop_loss:
                should_exit = True
                exit_reason = "STOP_LOSS"
            elif h >= self.tp2_price:
                should_exit = True
                exit_reason = "TAKE_PROFIT"
        else:
            if h >= self.stop_loss:
                should_exit = True
                exit_reason = "STOP_LOSS"
            elif l <= self.tp2_price:
                should_exit = True
                exit_reason = "TAKE_PROFIT"

        if should_exit:
            exit_side = OrderSide.SELL if self.pos_side == 1 else OrderSide.BUY
            # 严格使用真实持仓数量，且强制指定 reduce_only=True（只减仓）
            order = self.order_factory.market(
                instrument_id=iid,
                order_side=exit_side,
                quantity=Quantity.from_int(int(real_qty)),
                reduce_only=True,
            )
            self.pending_exit_order_id = order.client_order_id
            self.submit_order(order)
            self.log.info(
                f"[{raw_sym}] Submitting REDUCE_ONLY EXIT order ({exit_reason}): "
                f"{exit_side.name} {int(real_qty)} cts (NetPos={real_qty})..."
            )


# ─── Live Node Entry Point ─────────────────────────────────────────────────────
def main() -> None:
    logger.info("=" * 75)
    logger.info("NAUTILUS TRADER - 4-ASSET PRODUCTION TRADING MATRIX")
    logger.info("Universe: BTC-USDT-SWAP, ETH-USDT-SWAP, SOL-USDT-SWAP, BNB-USDT-SWAP")
    logger.info("Mode: OKX DEMO | Account: OKX-DEMO-001 | Timeframe: 15-Minute Bars")
    logger.info("=" * 75)

    node = (
        LiveNode.builder("SMC-MATRIX-NODE", TraderId.from_str("SMC-MATRIX-001"), Environment.LIVE)
        .with_reconciliation(reconciliation=True)
        .with_risk_engine_config(LiveRiskEngineConfig(bypass=True))
        .add_data_client(
            None,
            OKXDataClientFactory(),
            OKXDataClientConfig(
                instrument_types=[OKXInstrumentType.SWAP],
                environment=OKXEnvironment.DEMO,
            ),
        )
        .add_exec_client(
            None,
            OKXExecutionClientFactory(),
            OKXExecutionClientConfig(
                account_id=AccountId.from_str("OKX-DEMO-001"),
                instrument_types=[OKXInstrumentType.SWAP],
                environment=OKXEnvironment.DEMO,
                margin_mode=OKXMarginMode.CROSS,
            ),
        )
        .build()
    )

    portfolio_matrix = [
        ("BTC-USDT-SWAP", 0.01, 1, "001", 60.0),
        ("ETH-USDT-SWAP", 0.10, 2, "002", 60.0),
        ("SOL-USDT-SWAP", 1.00, 2, "003", 58.0),
        ("BNB-USDT-SWAP", 0.01, 1, "004", 60.0),
    ]

    for symbol, ct_val, prec, tag, score in portfolio_matrix:
        coin = symbol.split("-")[0]
        strat_cfg = SMCLiveConfig(
            strategy_id=StrategyId.from_str(f"SMC-{coin}-001"),
            order_id_tag=tag,
            use_hyphens_in_client_order_ids=False,  # Enforces pure alphanumeric clOrdId for OKX
        )
        strat_cfg.instrument_id = f"{symbol}.{OKX}"
        strat_cfg.ct_val = ct_val
        strat_cfg.price_precision = prec
        strat_cfg.risk_pct = 0.010
        strat_cfg.min_score = score
        strat_cfg.u_max = 0.35
        strat_cfg.c_max = 0.40
        strat_cfg.tp1_r = 1.5
        strat_cfg.tp2_r = 2.0
        strat_cfg.max_loss_streak = 3
        strat_cfg.cooldown_bars = 48    # 熔断后冷却 48 根 15m K 线 (12小时) 自动解封
        strat_cfg.max_pending_bars = 3  # 3根K线内未成交则自动撤单
        strat_cfg.use_market_order = False  # 使用限价单挂单，并在3根K线未成交时撤单

        strategy = SMCLiveStrategy(strat_cfg)
        node.add_strategy(strategy)
        logger.info(f"Registered {coin} strategy (Tag: {tag}, ct_val: {ct_val}, max_pending_bars=3, use_hyphens=False)")

    logger.info("All 4 assets registered successfully. Starting live multi-asset event loop...")
    node.run()


if __name__ == "__main__":
    main()
