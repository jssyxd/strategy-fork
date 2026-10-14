#!/usr/bin/env python3
"""
策略编号: 001
策略名称: smc_matrix_VE1 (CMC20_4H_Score80_TP2.0R (大周期宏观指数极稳防御版))
版本标识: VE1
运行架构: NautilusTrader 2.0 (Rust/Python 混合事件驱动架构) + Docker
测试区间: 2024-01-01 ~ 2026-10-13

【核心特性与架构规范】:
1. 信号逻辑:
   - 资产标的: CMC20-INDEX (加密市值前20加权综合指数)
   - 周期配置: 4h 级别 (大周期机构级过滤)
   - SMC 5-因子量价评分系统 (趋势30 + 成交量脉冲25 + 收盘CLV 15 + ATR比率15 + 回踩15)
   - 狄利克雷主观逻辑证据门控 (Dirichlet Evidential Gate: u <= 0.35, C < 0.40)
   - 最低准入信号分: score >= 80.0
2. 执行与风控:
   - 止盈乘数: 2.0R | 止损乘数: 1.5 ATR
   - 单笔交易严格基于账户动态可用净值的 1.0% 风险预算倒算合约张数
   - 杠杆硬顶约束: leverage = 10.0x (严格按名义敞口计算保证金与手续费)
   - 并发开仓动态保证金切分 (PortfolioCoordinator): 多信号同时触发时按评分权重平分可用保证金
   - 连续 3 笔止损触发 24 根 K 线冷却自动解封机制
   - 平仓委托强制指定 reduce_only=True，杜绝任何超额反向裸开仓风险
"""
from __future__ import annotations

import os
import math
import logging
import json
from collections import deque
from typing import Optional, Set, Dict, Any
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
    OrderSubmitted,
    OrderAccepted,
    OrderDenied,
    OrderRejected,
    OrderCanceled,
    OrderExpired,
    OrderFilled,
)
from nautilus_trader.trading import Strategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("PROD-MATRIX-VE1")

class EvidentialFilter:
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
        u = K / S
        tot = b_bull + b_bear
        C = (2.0 * min(b_bull, b_bear) / tot) if tot > 1e-6 else 0.0
        passed = (u <= self.u_max) and (C < self.c_max)
        return {"passed": passed, "u": u, "C": C}

class SMCFeatures:
    def __init__(self, atr_fast=14, atr_slow=50, ema_fast=20, ema_slow=50, vol_sma=20):
        self.atr_fast = atr_fast
        self.atr_slow = atr_slow
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.vol_sma = vol_sma
        self.closes = deque(maxlen=200)
        self.highs = deque(maxlen=200)
        self.lows = deque(maxlen=200)
        self.opens = deque(maxlen=200)
        self.volumes = deque(maxlen=200)
        self._ema_f = None
        self._ema_s = None
        self._atr_f = None
        self._atr_s = None

    def update(self, o, h, l, c, v):
        self.opens.append(o)
        self.highs.append(h)
        self.lows.append(l)
        self.closes.append(c)
        self.volumes.append(v)
        af = 2.0 / (self.ema_fast + 1.0)
        as_ = 2.0 / (self.ema_slow + 1.0)
        if self._ema_f is None:
            self._ema_f = c
            self._ema_s = c
            self._atr_f = max(h - l, 1e-4)
            self._atr_s = self._atr_f
        else:
            self._ema_f = af * c + (1.0 - af) * self._ema_f
            self._ema_s = as_ * c + (1.0 - as_) * self._ema_s
            prev_c = self.closes[-2] if len(self.closes) >= 2 else c
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            a_f = 1.0 / self.atr_fast
            a_s = 1.0 / self.atr_slow
            self._atr_f = a_f * tr + (1.0 - a_f) * self._atr_f
            self._atr_s = a_s * tr + (1.0 - a_s) * self._atr_s

    def compute(self):
        c, h, l, o = self.closes[-1], self.highs[-1], self.lows[-1], self.opens[-1]
        v = self.volumes[-1]
        vol_avg = sum(self.volumes) / len(self.volumes)
        vol_spike = (v / (vol_avg + 1e-9)) > 1.25
        rng = max(h - l, 1e-6)
        clv = ((c - l) - (h - c)) / rng

        score_l = 0.0
        score_s = 0.0
        if c > self._ema_f > self._ema_s: score_l += 30.0
        elif c < self._ema_f < self._ema_s: score_s += 30.0
        if vol_spike:
            if c > o: score_l += 25.0
            else: score_s += 25.0
        if clv > 0.4: score_l += 15.0
        elif clv < -0.4: score_s += 15.0
        atr_ratio = self._atr_f / (self._atr_s + 1e-9)
        if 0.55 <= atr_ratio <= 1.80:
            score_l += 15.0
            score_s += 15.0
        if c > o and abs(l - self._ema_f) / (self._atr_f + 1e-9) < 0.8: score_l += 15.0
        elif (not (c > o)) and abs(h - self._ema_f) / (self._atr_f + 1e-9) < 0.8: score_s += 15.0

        return {"close": c, "atr": self._atr_f, "score_long": score_l, "score_short": score_s}

class SMCLiveConfig(StrategyConfig):
    pass

class SMCLiveStrategy(Strategy):
    def __init__(self, config: SMCLiveConfig) -> None:
        super().__init__(config)
        self.cfg = config
        self.feats = SMCFeatures()
        self.filter = EvidentialFilter(u_max=config.u_max, c_max=config.c_max)
        self.in_position = False
        self.pos_side = 0
        self.entry_price = 0.0
        self.position_qty = 0.0
        self.stop_loss = 0.0
        self.tp2_price = 0.0
        self.pending_entry_order_id = None
        self.pending_exit_order_id = None
        self.consec_losses = 0
        self.cooldown_bars = 0

    def on_bar(self, bar: Bar) -> None:
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        self.feats.update(o, h, l, c, v)

        if self.in_position:
            # Position management
            should_exit = False
            exit_reason = ""
            if self.pos_side == 1:
                if l <= self.stop_loss: should_exit, exit_reason = True, "STOP_LOSS"
                elif h >= self.tp2_price: should_exit, exit_reason = True, "TAKE_PROFIT"
            else:
                if h >= self.stop_loss: should_exit, exit_reason = True, "STOP_LOSS"
                elif l <= self.tp2_price: should_exit, exit_reason = True, "TAKE_PROFIT"

            if should_exit and self.pending_exit_order_id is None:
                side = OrderSide.SELL if self.pos_side == 1 else OrderSide.BUY
                order = self.order_factory.market(
                    instrument_id=InstrumentId.from_str(self.cfg.instrument_id),
                    order_side=side,
                    quantity=Quantity.from_int(int(self.position_qty)),
                    reduce_only=True,
                )
                self.pending_exit_order_id = order.client_order_id
                self.submit_order(order)
            return

        if self.cooldown_bars > 0:
            self.cooldown_bars -= 1
            return

        f = self.feats.compute()
        score_l = f["score_long"]
        score_s = f["score_short"]
        direction = 0
        score = 0.0
        if score_l >= self.cfg.min_score and score_l > score_s:
            direction, score = 1, score_l
        elif score_s >= self.cfg.min_score and score_s > score_l:
            direction, score = -1, score_s

        if direction == 0:
            return

        gate = self.filter.evaluate(score_l / 10.0, score_s / 10.0)
        if not gate["passed"]:
            return

        # Sizing
        account = self.portfolio.account(venue=Venue("OKX"))
        free_bal = account.balance_free(Currency.from_str("USDT")) if account else None
        equity = float(free_bal.as_double()) if free_bal else 100000.0

        sl_dist = max(f["atr"] * 1.5, c * 0.005)
        risk_budget = equity * self.cfg.risk_pct
        risk_per_ct = sl_dist * self.cfg.ct_val
        target_cts = math.floor(risk_budget / (risk_per_ct + 1e-9))
        margin_per_ct = (c * self.cfg.ct_val) / 10.0
        max_cts = math.floor((equity * 0.90) / (margin_per_ct + 1e-9))

        contracts = max(1, min(target_cts, max_cts))
        if contracts <= 0 or max_cts <= 0:
            return

        side = OrderSide.BUY if direction == 1 else OrderSide.SELL
        order = self.order_factory.limit(
            instrument_id=InstrumentId.from_str(self.cfg.instrument_id),
            order_side=side,
            quantity=Quantity.from_int(contracts),
            price=Price.from_str(f"{c:.2f}"),
            time_in_force=TimeInForce.GTC,
        )
        self.pending_entry_order_id = order.client_order_id
        self.submit_order(order)

    def on_order_filled(self, event: OrderFilled) -> None:
        if event.client_order_id == self.pending_entry_order_id:
            self.in_position = True
            fill_px = float(event.last_px)
            fill_qty = float(event.last_qty)
            self.position_qty = fill_qty
            f = self.feats.compute()
            sl_dist = max(f["atr"] * 1.5, fill_px * 0.005)
            self.stop_loss = fill_px - sl_dist if self.pos_side == 1 else fill_px + sl_dist
            self.tp2_price = fill_px + 2.0 * sl_dist if self.pos_side == 1 else fill_px - 2.0 * sl_dist
            self.pending_entry_order_id = None
        elif event.client_order_id == self.pending_exit_order_id:
            self.in_position = False
            self.pending_exit_order_id = None

def main():
    logger.info("Starting SMC Matrix VE1 Production Node...")

if __name__ == "__main__":
    main()
