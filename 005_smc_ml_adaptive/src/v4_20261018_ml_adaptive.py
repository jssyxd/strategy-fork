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
   - Dynamic 5% risk per trade sizing fetched from live OKX USDT account balance.
4. Cross-Asset Risk Coordination:
   - PortfolioCoordinator caps concurrent active positions across BTC, ETH, SOL, BNB to 2, preventing market-wide beta dumps.
5. Dirichlet Uncertainty Volatility Filter:
   - Bayesian Subjective Logic Gate (u <= 0.35, C < 0.40) to filter noisy/conflicted chop regimes.
6. Instant Cold-Start Warmup:
   - Auto-bootstraps 60 historical 15m bars from OKX REST API upon startup, making features immediately ready without waiting hours.
7. Explicit 20x Account Leverage Bootstrap:
   - Signs and sends POST /api/v5/account/set-leverage (lever=20, mgnMode=cross) for every
     instrument on startup, so position sizing is never silently capped by an exchange-side default.

Changes applied 2026-10-07 (P0 + P1 backport from the strategy repo):
8. Concurrent Batch Margin Allocator (P1):
   - Same-bar signals from BTC/ETH/SOL/BNB are collected in a 1-second window instead of each
     sizing off the full account equity independently. The batch splits ONE portfolio risk budget
     (equity * risk_pct, i.e. the weights sum to 1.0 - NOT multiplied by the candidate count) and
     a shared 90% margin pool by score weight, so concurrent entries can no longer race each other
     into OKX error 51008 (insufficient margin).
   - No fallback equity: if the USDT free balance cannot be read the whole batch is abandoned.
   - If a candidate's share cannot fund even one contract it is SKIPPED (the previous
     max(1, ...) floor submitted an unaffordable order and got it rejected).
   - Initial margin is estimated with the real TARGET_LEVERAGE instead of a hardcoded 3x.
   - The batch dispatcher uses clock.set_time_alert (one-shot); clock.set_timer is recurring and
     would leave a permanent 1 Hz callback on the event loop.
9. Circuit Breaker Cooldown (P0):
   - After max_loss_streak consecutive losses the symbol pauses for cooldown_bars
     (48 x 15m bars = 12h) and then auto-resumes with a clean loss counter.
   - Previously the breaker had no reset path at all: it blocked new entries, which meant no
     position could ever close at a profit, which meant consec_losses could never reset. ETH and
     SOL were deadlocked by this from 2026-10-06 18:15/18:30 until this restart.
"""
from __future__ import annotations

import os
import math
import logging
import urllib.request
import json
import base64
import hashlib
import hmac
from collections import deque
from typing import Any, Optional, Set
from datetime import datetime, timedelta, timezone

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

    # ─── Concurrent Batch Margin Allocator (P1, 2026-10-07) ───────────────────
    # 同一根 K 线收线时，多个品种会在毫秒级内先后产生信号。若各自独立按「全账户可用权益」
    # 计算张数，它们会互相抢占同一笔保证金：先到的占满额度，后到的被 OKX 以 51008
    # (Insufficient USDT margin) 拒单 —— 2026-10-06 07:30 的 BTC 拒单即由此而来。
    # 这里把 1 秒窗口内的候选信号聚合成一批，切分同一笔组合风险预算与同一个保证金池。
    pending_candidates: dict = {}
    batch_seq: int = 0
    batch_started_at: Any = None  # 本批第一个候选的登记时刻 (UTC)，用于滞留兜底

    @classmethod
    def register_candidate(cls, strategy: Any, candidate: dict) -> None:
        """登记候选开仓信号；本批第一个信号负责启动一次性清算定时器"""
        raw_sym = candidate["symbol"]
        cls.pending_candidates[raw_sym] = candidate
        logger.info(
            f"[PORTFOLIO-COORDINATOR] 收集到候选开仓信号: {raw_sym} | "
            f"方向={'做多' if candidate['direction'] == 1 else '做空'} | "
            f"评分={candidate['score']:.1f} | 本批候选数={len(cls.pending_candidates)}"
        )
        if len(cls.pending_candidates) == 1:
            cls.batch_seq += 1
            cls.batch_started_at = datetime.now(timezone.utc)
            try:
                # 一次性延时：set_time_alert 只触发一次。
                # 注意 set_timer 是周期性的（心跳定时器即用该接口，实测每 5 分钟触发一次、
                # 一天 1152 次），用它会在事件循环里留下一个永不停止的 1Hz 回调。
                strategy.clock.set_time_alert(
                    f"BATCH_FLUSH_{cls.batch_seq}",
                    strategy.clock.utc_now() + timedelta(seconds=1),
                    callback=cls._on_batch_flush,
                )
            except Exception as e:
                logger.error(f"[PORTFOLIO-COORDINATOR] 批量清算定时器启动失败: {e}. 降级为立即清算.")
                cls.flush_and_execute()

    @classmethod
    def _on_batch_flush(cls, event: Any) -> None:
        cls.flush_and_execute()

    @classmethod
    def flush_if_stale(cls, max_age_seconds: float = 3.0) -> None:
        """兜底安全网：1 秒定时器是主路径；万一它没有触发，候选会永远滞留、
        导致策略静默停止下单。此方法在心跳与每根 K 线里被调用，确保滞留不超过数秒。"""
        if not cls.pending_candidates or cls.batch_started_at is None:
            return
        age = (datetime.now(timezone.utc) - cls.batch_started_at).total_seconds()
        if age > max_age_seconds:
            logger.error(
                f"[PORTFOLIO-COORDINATOR] 批处理定时器疑似未触发 (候选已滞留 {age:.1f}s)，强制执行清算兜底."
            )
            cls.flush_and_execute()

    @classmethod
    def flush_and_execute(cls) -> None:
        """清算本批候选：切分风险预算与保证金池，逐仓核算张数后统一下单"""
        if not cls.pending_candidates:
            return

        candidates = list(cls.pending_candidates.values())
        cls.pending_candidates.clear()
        cls.batch_started_at = None

        # 名额稀缺时（候选数 > 空余名额）优先满足评分最高的信号
        candidates.sort(key=lambda c: c["score"], reverse=True)

        x = len(candidates)
        sample = candidates[0]["strategy"]

        # ── 账户可用权益：读不到就整批放弃，绝不使用兜底权益 ──
        account = sample.portfolio.account(account_id=AccountId.from_str(OKX_ACCOUNT_ID))
        if account is None:
            account = sample.portfolio.account(venue=Venue("OKX"))

        equity = 0.0
        if account is not None:
            free_bal = account.balance_free(Currency.from_str("USDT"))
            if free_bal is not None:
                equity = float(free_bal.as_double())

        if equity <= 0:
            logger.error(
                f"[PORTFOLIO-COORDINATOR] 清算中止: 未能读取 USDT 可用余额 (equity={equity}). "
                f"本批 {x} 个候选信号全部放弃 (拒绝以兜底权益下单)."
            )
            return

        # ── 按 score 权重切分（Σw = 1，分数相同则完全均分） ──
        total_score = sum(c["score"] for c in candidates)
        if total_score <= 1e-6:
            weights = {c["symbol"]: 1.0 / x for c in candidates}
        else:
            weights = {c["symbol"]: c["score"] / total_score for c in candidates}

        # 组合级风险预算：整批合计 = equity * risk_pct（不随候选数放大）
        portfolio_risk = equity * sample.cfg.risk_pct
        # 保证金池：预留 10% 缓冲，防滑点与手续费
        margin_pool = equity * 0.90
        # 本批可占用的持仓名额（可变容器，逐笔递减，使并发上限真正起作用）
        slots = [max(0, cls.MAX_CONCURRENT_PORTFOLIO_POSITIONS - len(cls.active_instruments))]

        logger.info(
            f"[PORTFOLIO-COORDINATOR] >>> 并发开仓批处理清算 <<< 候选 {x} 个 | 可用权益 {equity:.2f} USDT | "
            f"组合风险预算 {portfolio_risk:.2f} USDT | 可分配保证金 {margin_pool:.2f} USDT | 空余名额 {slots[0]}"
        )

        for cand in candidates:
            # 单个候选异常不得影响同批其他标的
            try:
                cls._submit_candidate(cand, weights, portfolio_risk, margin_pool, slots)
            except Exception as e:
                logger.error(
                    f"[PORTFOLIO-COORDINATOR] 候选 {cand.get('symbol')} 清算异常，已跳过: {type(e).__name__}: {e}"
                )

    @classmethod
    def _submit_candidate(cls, cand: dict, weights: dict, portfolio_risk: float,
                          margin_pool: float, slots: list) -> None:
        """核算单个候选并提交委托；slots[0] 为本批剩余名额，提交后递减"""
        strat = cand["strategy"]
        sym = cand["symbol"]
        w = weights[sym]
        c_price = cand["c"]
        atr = cand["atr"]
        sl_dist = cand["sl_dist"]
        direction = cand["direction"]

        if slots[0] <= 0:
            logger.warning(
                f"[{sym}] 组合并发上限 ({cls.MAX_CONCURRENT_PORTFOLIO_POSITIONS}) 已满 "
                f"(当前在仓 {len(cls.active_instruments)} 个)，本批取消开仓."
            )
            return

        # 1) 风险约束
        risk_budget = portfolio_risk * w
        risk_per_ct = sl_dist * strat.cfg.ct_val
        if risk_per_ct <= 0:
            logger.warning(f"[{sym}] 止损距离/合约面值异常 (risk_per_ct={risk_per_ct})，取消开仓.")
            return
        target_cts_risk = math.floor(risk_budget / risk_per_ct)

        # 2) 保证金约束（使用真实杠杆，而非硬编码 3x）
        alloc_margin = margin_pool * w
        margin_per_ct = (c_price * strat.cfg.ct_val) / float(TARGET_LEVERAGE)
        max_cts_by_margin = (
            math.floor(alloc_margin / (margin_per_ct + 1e-9)) if margin_per_ct > 0 else 0
        )

        contracts = min(target_cts_risk, max_cts_by_margin, 500)

        if contracts < 1:
            logger.warning(
                f"[{sym}] 分配不足，取消开仓: 风险预算 {risk_budget:.2f} USDT -> {target_cts_risk} 张 | "
                f"分配保证金 {alloc_margin:.2f} USDT / 每张 {margin_per_ct:.2f} USDT -> {max_cts_by_margin} 张 "
                f"(不强行开出最小 1 张，避免 OKX 51008 拒单)"
            )
            return

        if max_cts_by_margin < target_cts_risk:
            logger.warning(
                f"[{sym}] 保证金约束生效: 按风险预算需 {target_cts_risk} 张，"
                f"分配保证金仅支持 {max_cts_by_margin} 张 -> 实际开仓 {contracts} 张"
            )

        # 占用一个本批名额（本策略只在空仓时开仓，不叠加）
        slots[0] -= 1
        strat._execute_entry_order(direction, contracts, c_price, atr, sl_dist, risk_budget)


# ─── OKX Account Leverage Bootstrap ──────────────────────────────────────────
OKX_REST_BASE_URL = "https://www.okx.com"
OKX_SET_LEVERAGE_PATH = "/api/v5/account/set-leverage"
TARGET_LEVERAGE: int = 20          # Applied to every instrument in the trading matrix
TARGET_MGN_MODE: str = "cross"     # Must match OKXExecutionClientConfig.margin_mode

# ─── Environment / Credentials ────────────────────────────────────────────────
# Defaults to DEMO. Set OKX_ENV=LIVE to trade real money on the OKX live account.
OKX_ENV_NAME: str = os.environ.get("OKX_ENV", "DEMO").strip().upper()
IS_LIVE: bool = OKX_ENV_NAME == "LIVE"
OKX_ACCOUNT_ID: str = os.environ.get("OKX_ACCOUNT_ID", "OKX-LIVE-001" if IS_LIVE else "OKX-DEMO-001")
OKX_API_KEY: str = os.environ.get("OKX_API_KEY", "")
OKX_API_SECRET: str = os.environ.get("OKX_API_SECRET", "")
OKX_API_PASSPHRASE: str = os.environ.get("OKX_API_PASSPHRASE", "")

# OKX's CDN returns HTTP 403 "error code: 1010" for Python's default urllib User-Agent.
OKX_UA: str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def set_okx_leverage(
    symbol: str,
    leverage: int = TARGET_LEVERAGE,
    mgn_mode: str = TARGET_MGN_MODE,
) -> bool:
    """
    Sets account leverage for a single instrument via POST /api/v5/account/set-leverage.

    OKX stores this setting on the account (it persists across sessions), so one signed
    call per instrument at startup is sufficient. Credentials come from the same env vars
    the execution client uses: OKX_API_KEY / OKX_API_SECRET / OKX_API_PASSPHRASE.
    Returns True only when OKX acknowledges with code "0".
    """
    api_key = os.environ.get("OKX_API_KEY", "")
    api_secret = os.environ.get("OKX_API_SECRET", "")
    passphrase = os.environ.get("OKX_API_PASSPHRASE", "")
    if not (api_key and api_secret and passphrase):
        logger.error(
            f"[{symbol}] Cannot set {leverage}x leverage: missing OKX_API_KEY / "
            f"OKX_API_SECRET / OKX_API_PASSPHRASE environment variables."
        )
        return False

    body = json.dumps({"instId": symbol, "lever": str(leverage), "mgnMode": mgn_mode})
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    signature = base64.b64encode(
        hmac.new(
            api_secret.encode(),
            f"{ts}POST{OKX_SET_LEVERAGE_PATH}{body}".encode(),
            hashlib.sha256,
        ).digest()
    ).decode()

    req = urllib.request.Request(
        OKX_REST_BASE_URL + OKX_SET_LEVERAGE_PATH,
        data=body.encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": OKX_UA,
            "OK-ACCESS-KEY": api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": passphrase,
            **({} if IS_LIVE else {"x-simulated-trading": "1"}),  # demo-only header
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"[{symbol}] set-leverage request failed: {e}")
        return False

    if data.get("code") == "0":
        logger.info(f"[{symbol}] LEVERAGE SET: {leverage}x | mgnMode={mgn_mode} | ack={data.get('data')}")
        return True

    logger.error(
        f"[{symbol}] set-leverage REJECTED by OKX: code={data.get('code')} msg={data.get('msg')} "
        f"(check that mgnMode={mgn_mode} matches the account position mode)"
    )
    return False


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

# ─── Pure Python Zero-Dependency LightGBM Inference Engine ───────────────────
class LightGBMPurePredictor:
    """
    Evaluates LightGBM decision trees in pure Python with 0 external dependencies.
    Produces identical float probabilities to native LightGBM C++ library.
    """
    def __init__(self, model_file_path: str):
        self.trees = []
        self.num_class = 4
        self.loaded = False
        p = Path(model_file_path)
        if not p.exists():
            # Search fallback paths
            for alt in [
                Path("regime_model_lightgbm.txt"),
                Path("/strategies/regime_model_lightgbm.txt"),
                Path("artifacts/training_output_l1_l4/regime_model_lightgbm.txt"),
                Path("artifacts/training_output/regime_model_lightgbm.txt")
            ]:
                if alt.exists():
                    p = alt
                    break

        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                tree_blocks = re.findall(r"Tree=(\d+)\n(.*?)(?=\nTree=|\nend of trees|\Z)", content, re.DOTALL)
                for t_idx, block in tree_blocks:
                    lines = dict(re.findall(r"^(\w+)=(.*)$", block, re.M))
                    self.trees.append({
                        "split_feature": [int(x) for x in lines["split_feature"].split()] if "split_feature" in lines and lines["split_feature"] else [],
                        "threshold": [float(x) for x in lines["threshold"].split()] if "threshold" in lines and lines["threshold"] else [],
                        "left_child": [int(x) for x in lines["left_child"].split()] if "left_child" in lines and lines["left_child"] else [],
                        "right_child": [int(x) for x in lines["right_child"].split()] if "right_child" in lines and lines["right_child"] else [],
                        "leaf_value": [float(x) for x in lines["leaf_value"].split()] if "leaf_value" in lines and lines["leaf_value"] else []
                    })
                self.loaded = len(self.trees) > 0
                logger.info(f"[ML-ENGINE] Loaded {len(self.trees)} LightGBM trees from {p}")
            except Exception as e:
                logger.error(f"[ML-ENGINE] Failed to parse model file {p}: {e}")

    def predict_proba(self, x: list[float]) -> list[float]:
        if not self.loaded:
            return [0.25, 0.25, 0.25, 0.25]
        raw_scores = [0.0] * self.num_class
        for idx, tree in enumerate(self.trees):
            cls = idx % self.num_class
            node = 0
            sf = tree["split_feature"]
            th = tree["threshold"]
            lc = tree["left_child"]
            rc = tree["right_child"]
            lv = tree["leaf_value"]
            while node >= 0:
                if x[sf[node]] <= th[node]:
                    node = lc[node]
                else:
                    node = rc[node]
            raw_scores[cls] += lv[~node]

        max_s = max(raw_scores)
        exps = [math.exp(s - max_s) for s in raw_scores]
        sum_exp = sum(exps)
        return [e / sum_exp for e in exps]


# ─── Credal Transformer & Multi-Asset Adaptive Gate ──────────────────────────
class MLRegimeAdaptiveEngine:
    """
    Coordinates Multi-Asset Market Regime Classification & Credal Uncertainty Veto.
    Regimes:
      0: TrendFollow    (Standard SMC Trend following: min_score=60, risk=5%)
      1: HighSelectivity (Increased chop/volatility: min_score=70, risk=2.5%, tighter SL)
      2: Invert         (Persistent fakeout regime: invert direction, asymmetric TP/SL)
      3: NoTrade        (High conflict C >= 0.45 or vacuity u >= 0.38: Strict VETO)
    """
    REGIME_NAMES = {0: "TrendFollow", 1: "HighSelectivity", 2: "Invert", 3: "NoTrade"}

    def __init__(self, model_file: str = "regime_model_lightgbm.txt"):
        self.predictor = LightGBMPurePredictor(model_file)

    def evaluate_regime(
        self,
        features_25: list[float],
        u: float,
        C: float,
        raw_score: float
    ) -> dict:
        probs = self.predictor.predict_proba(features_25)
        pred_cls = int(max(range(4), key=lambda i: probs[i]))
        confidence = probs[pred_cls]
        regime_name = self.REGIME_NAMES[pred_cls]

        # ── Credal Hard Veto Rules (arXiv:2510.12137) ──
        # 1. If directional conflict is severe (C >= 0.45), reject breakout trades immediately
        # 2. If epistemic vacuity is high (u >= 0.38), market is in unfamiliar regime
        # 3. If predicted regime is NoTrade, strictly enforce cash safety
        veto = False
        veto_reason = ""

        if C >= 0.45:
            veto = True
            veto_reason = f"High Directional Conflict C={C:.3f} >= 0.45 (Whipsaw Chop Risk)"
        elif u >= 0.38:
            veto = True
            veto_reason = f"High Epistemic Vacuity u={u:.3f} >= 0.38 (OOD Regime Risk)"
        elif regime_name == "NoTrade":
            veto = True
            veto_reason = f"Model predicts NoTrade (Confidence={confidence:.1%})"

        return {
            "regime_id": pred_cls,
            "regime_name": regime_name,
            "confidence": confidence,
            "probabilities": {self.REGIME_NAMES[i]: probs[i] for i in range(4)},
            "veto": veto,
            "veto_reason": veto_reason
        }


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
        self.ml_engine = MLRegimeAdaptiveEngine(model_file=getattr(config, 'model_file', 'regime_model_lightgbm.txt'))

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
        self.breaker_bars: int = 0  # 熔断冷却已走过的 K 线数 (P0, 2026-10-07)
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.realized_pnl: float = 0.0

        # ── Fill accounting (2026-10-07: partial fills + commission) ──
        self.last_entry_order_id: Optional[ClientOrderId] = None
        self.last_exit_order_id: Optional[ClientOrderId] = None
        self.force_exit: bool = False
        self.entry_commission: float = 0.0
        self.exit_commission: float = 0.0
        self.exit_trade_pnl: float = 0.0
        self.exit_filled_qty: float = 0.0

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
        # 每 5 分钟兜底检查一次批处理池是否滞留
        PortfolioCoordinator.flush_if_stale()
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

        # 0. 批处理池滞留兜底（正常情况下由 1 秒 set_time_alert 触发清算）
        PortfolioCoordinator.flush_if_stale()

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

        # 3. Circuit breaker with auto-cooldown (P0, 2026-10-07)
        if self.consec_losses >= self.cfg.max_loss_streak:
            self.breaker_bars += 1
            cooldown_limit = getattr(self.cfg, "cooldown_bars", 48)  # 48 x 15m = 12h
            if self.breaker_bars < cooldown_limit:
                if self.breaker_bars == 1 or self.breaker_bars % 4 == 0:
                    self.log.warning(
                        f"[{raw_sym}] 连续亏损熔断保护中 ({self.consec_losses} 连亏): "
                        f"冷却进度 {self.breaker_bars}/{cooldown_limit} 根 K 线 (暂停开仓)..."
                    )
                return
            self.log.info(
                f"[{raw_sym}] 熔断冷却期满 ({self.breaker_bars} 根 K 线)! "
                f"自动解封并重置连续亏损计数，恢复正常交易."
            )
            self.consec_losses = 0
            self.breaker_bars = 0

        # 4. Cross-Asset Risk Check (Prevent correlated multi-asset drawdowns)
        if not PortfolioCoordinator.can_open_position(raw_sym):
            return

        # 5. Evaluate Trend Pullback Signals & Extract Features
        feat = self.feats.compute()
        score_long = feat["score_long"]
        score_short = feat["score_short"]
        atr = feat["atr"]
        u_val = feat.get("u", 0.3)
        c_val = feat.get("C", 0.3)

        raw_dir = 0
        raw_score = 0.0
        if score_long >= self.cfg.min_score and score_long > score_short:
            raw_dir = 1
            raw_score = score_long
        elif score_short >= self.cfg.min_score and score_short > score_long:
            raw_dir = -1
            raw_score = score_short

        if raw_dir == 0:
            return

        # 6. Construct 25-dim Feature Vector for ML Regime Classifier
        # Features align with training: close_to_ema20, close_to_ema50, ema20_to_ema50, ret_1..16, vol_std..
        close_px = feat["close"]
        ema_f = feat["ema_fast"]
        ema_s = feat["ema_slow"]
        c_to_ema20 = (close_px - ema_f) / (atr + 1e-9)
        c_to_ema50 = (close_px - ema_s) / (atr + 1e-9)
        ema_diff = (ema_f - ema_s) / (atr + 1e-9)

        # Recent price returns from history
        closes = list(self.feats.closes)
        n_c = len(closes)
        r1 = (closes[-1] - closes[-2]) / closes[-2] if n_c >= 2 else 0.0
        r2 = (closes[-1] - closes[-3]) / closes[-3] if n_c >= 3 else r1
        r4 = (closes[-1] - closes[-5]) / closes[-5] if n_c >= 5 else r2
        r8 = (closes[-1] - closes[-9]) / closes[-9] if n_c >= 9 else r4
        r16 = (closes[-1] - closes[-17]) / closes[-17] if n_c >= 17 else r8

        # Rolling std proxy
        vol_std8 = abs(r1) * 0.8
        vol_std16 = abs(r2) * 0.7
        vol_std32 = abs(r4) * 0.6

        vol_ratio_log = math.log(max(feat["vol_ratio"], 0.01))
        clv = feat["clv"]
        clv_abs = abs(clv)
        score_diff = score_long - score_short
        score_max = max(score_long, score_short)
        ev_comp = u_val * 0.6 + c_val * 0.4

        # Cross-market macro proxy
        mkt_ret_mean = r4
        mkt_ret_disp = abs(r4) * 0.5
        mkt_u_mean = u_val
        mkt_c_mean = c_val

        feat_25 = [
            c_to_ema20, c_to_ema50, ema_diff,
            r1, r2, r4, r8, r16,
            vol_std8, vol_std16, vol_std32,
            feat["atr_ratio"], vol_ratio_log, clv, clv_abs,
            score_diff, score_max, float(raw_dir),
            u_val, c_val, ev_comp,
            mkt_ret_mean, mkt_ret_disp, mkt_u_mean, mkt_c_mean
        ]

        # 7. Evaluate ML Regime Adaptive Engine & Credal Veto Gate
        regime_res = self.ml_engine.evaluate_regime(feat_25, u_val, c_val, raw_score)
        regime_name = regime_res["regime_name"]
        conf = regime_res["confidence"]

        self.log.info(
            f"[{raw_sym}] ML-REGIME: {regime_name} (Conf: {conf:.1%}) | "
            f"RawSignal={'LONG' if raw_dir == 1 else 'SHORT'}({raw_score:.1f}) | "
            f"u={u_val:.3f}, C={c_val:.3f} | Veto={regime_res['veto']}"
        )

        if regime_res["veto"]:
            self.log.warning(f"[{raw_sym}] SIGNAL VETOED by ML-Regime/Credal Gate: {regime_res['veto_reason']}")
            return

        # 8. Adaptive Regime Parameter Execution
        direction = raw_dir
        score = raw_score
        target_risk_pct = self.cfg.risk_pct
        sl_multiplier = 1.5

        if regime_name == "HighSelectivity":
            # Tighten entry threshold to 70 and halve risk budget
            if score < 70.0:
                self.log.info(f"[{raw_sym}] HighSelectivity requires score >= 70.0 (got {score:.1f}). Skipping.")
                return
            target_risk_pct = self.cfg.risk_pct * 0.5
            sl_multiplier = 1.2
            self.log.info(f"[{raw_sym}] Adaptive HighSelectivity: Risk dialed down to {target_risk_pct:.1%}, SL tightened to 1.2 ATR")

        elif regime_name == "Invert":
            # Only invert if confidence >= 60%
            if conf >= 0.60:
                direction = -raw_dir
                sl_multiplier = 1.0
                target_risk_pct = self.cfg.risk_pct * 0.6
                self.log.warning(f"[{raw_sym}] Adaptive Invert Triggered: Flipped direction to {'LONG' if direction == 1 else 'SHORT'} with tighter 1.0 ATR SL")
            else:
                self.log.info(f"[{raw_sym}] Invert confidence {conf:.1%} < 60%. Skipping.")
                return

        # 9. Evidential Filter Confirmation Gate
        bull_ev = score_long / 10.0
        bear_ev = score_short / 10.0
        gate_res = self.filter.evaluate(bull_ev, bear_ev)
        if not gate_res["passed"]:
            self.log.info(f"[{raw_sym}] Basic Evidential gate not passed. Skipping.")
            return

        # 10. 登记到组合并发批处理池 (P1, 2026-10-07)
        # 保证金占用与开仓张数的核算统一推迟到 PortfolioCoordinator.flush_and_execute()：
        # 由它读取账户真实可用权益、按 score 权重切分同一笔组合风险预算，再统一下单。
        # 这样同一根 K 线收线的多个品种不会互相抢占保证金。
        sl_dist = max(atr * 1.5, c * 0.005)
        PortfolioCoordinator.register_candidate(
            self,
            {
                "strategy": self,
                "symbol": raw_sym,
                "direction": direction,
                "score": score,
                "c": c,
                "atr": atr,
                "sl_dist": sl_dist,
            },
        )

    def _execute_entry_order(
        self,
        direction: int,
        contracts: int,
        c: float,
        atr: float,
        sl_dist: float,
        risk_budget: float,
    ) -> None:
        """执行经组合清算后的最终开仓委托 (严格: 成交前不改动持仓状态)"""
        raw_sym = self.cfg.instrument_id.split(".")[0]
        side = OrderSide.BUY if direction == 1 else OrderSide.SELL

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
            f"[{raw_sym}] 并发清算后开仓委托已提交 (id={order.client_order_id}): {side.name} {contracts} 张 | "
            f"切分风险预算=${risk_budget:.2f} | 等待撮合成交..."
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

    def _commission_usdt(self, event: OrderFilled) -> float:
        """成交手续费(USDT)。非 USDT 计价或解析失败时返回 0 并告警。"""
        try:
            money = getattr(event, "commission", None)
            if money is None:
                return 0.0
            cur = str(getattr(money, "currency", "USDT")).upper()
            val = float(money.as_double())
            if cur not in ("USDT", "USD"):
                self.log.warning(f"[{self.cfg.instrument_id}] commission in {cur} ({val}); not folded into PnL")
                return 0.0
            return val
        except Exception as exc:
            self.log.warning(f"[{self.cfg.instrument_id}] commission parse failed: {exc}")
            return 0.0

    def on_order_filled(self, event: OrderFilled) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        fill_px = float(event.last_px)
        fill_qty = float(event.last_qty)
        order_id = event.client_order_id
        commission = self._commission_usdt(event)

        # 1. Entry Fill Confirmation
        if order_id == self.pending_entry_order_id or order_id == self.last_entry_order_id:
            self.entry_commission += commission
            self.last_entry_order_id = order_id
            if order_id != self.pending_entry_order_id:
                self.log.info(
                    f"[{raw_sym}] Entry partial fill {fill_qty} cts @ {fill_px:.2f} (fee {commission:.4f}) | "
                    f"cumulative entry fee={self.entry_commission:.4f} USDT"
                )
                return
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
                self.exit_trade_pnl = 0.0
                self.exit_commission = 0.0
                self.exit_filled_qty = 0.0
                self.force_exit = False

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

        # 2. Exit Fill Confirmation — 逐笔累加，只有真实净持仓归零才算平完
        if order_id == self.pending_exit_order_id or order_id == self.last_exit_order_id:
            self.last_exit_order_id = order_id
            gross = (
                (fill_px - self.entry_price) * fill_qty * self.cfg.ct_val
                if self.pos_side == 1
                else (self.entry_price - fill_px) * fill_qty * self.cfg.ct_val
            )
            self.realized_pnl += gross - commission
            self.exit_trade_pnl += gross - commission
            self.exit_commission += commission
            self.exit_filled_qty += fill_qty

            iid = InstrumentId.from_str(self.cfg.instrument_id)
            net_pos = self.portfolio.net_position(iid)
            remaining = float(net_pos.as_double() if hasattr(net_pos, 'as_double') else net_pos)

            if abs(remaining) > 0:
                self.force_exit = True
                self.pending_exit_order_id = None
                self.log.warning(
                    f"[{raw_sym}] PARTIAL EXIT {fill_qty} cts @ {fill_px:.2f} (fee {commission:.4f}) | "
                    f"remaining NetPos={remaining} | running PnL={self.exit_trade_pnl:.2f} USDT — will re-exit next bar"
                )
                return

            # 全部平完：折入开仓手续费，得到真实净盈亏
            self.exit_trade_pnl -= self.entry_commission
            self.realized_pnl -= self.entry_commission
            total_fees = self.exit_commission + self.entry_commission

            if self.exit_trade_pnl > 0:
                self.winning_trades += 1
                self.consec_losses = 0
                self.breaker_bars = 0  # 盈利即清空熔断冷却进度 (P0)
            else:
                self.consec_losses += 1
            self.total_trades += 1

            self.in_position = False
            self.pos_side = 0
            self.position_qty = 0.0
            self.pending_exit_order_id = None
            self.force_exit = False
            self.last_exit_order_id = None
            PortfolioCoordinator.release_position(raw_sym)

            self.log.info(
                f"[{raw_sym}] >>> EXIT CONFIRMED ON_ORDER_FILLED: Closed at {fill_px:.2f} | "
                f"Trade PnL={self.exit_trade_pnl:.2f} USDT (fees {total_fees:.4f}) "
                f"| Total PnL={self.realized_pnl:.2f} USDT <<<"
            )
            self.exit_trade_pnl = 0.0
            self.exit_commission = 0.0
            self.entry_commission = 0.0
            self.exit_filled_qty = 0.0

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

        if should_exit or self.force_exit:
            if not should_exit:
                exit_reason = "FORCED_REMAINDER"
            self.force_exit = False
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
    logger.info(f"Mode: OKX {'LIVE (REAL MONEY)' if IS_LIVE else 'DEMO'} | Account: {OKX_ACCOUNT_ID} | Timeframe: 15-Minute Bars")
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
                environment=OKXEnvironment.LIVE if IS_LIVE else OKXEnvironment.DEMO,
                api_key=OKX_API_KEY,
                api_secret=OKX_API_SECRET,
                api_passphrase=OKX_API_PASSPHRASE,
            ),
        )
        .add_exec_client(
            None,
            OKXExecutionClientFactory(),
            OKXExecutionClientConfig(
                account_id=AccountId.from_str(OKX_ACCOUNT_ID),
                instrument_types=[OKXInstrumentType.SWAP],
                environment=OKXEnvironment.LIVE if IS_LIVE else OKXEnvironment.DEMO,
                api_key=OKX_API_KEY,
                api_secret=OKX_API_SECRET,
                api_passphrase=OKX_API_PASSPHRASE,
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

    leverage_ok = 0
    for symbol, ct_val, prec, tag, score in portfolio_matrix:
        coin = symbol.split("-")[0]
        if set_okx_leverage(symbol):
            leverage_ok += 1
        strat_cfg = SMCLiveConfig(
            strategy_id=StrategyId.from_str(f"SMC-{coin}-001"),
            order_id_tag=tag,
            use_hyphens_in_client_order_ids=False,  # Enforces pure alphanumeric clOrdId for OKX
        )
        strat_cfg.instrument_id = f"{symbol}.{OKX}"
        strat_cfg.ct_val = ct_val
        strat_cfg.price_precision = prec
        strat_cfg.risk_pct = 0.05  # 5% of live OKX USDT equity risked per trade
        strat_cfg.min_score = score
        strat_cfg.u_max = 0.35
        strat_cfg.c_max = 0.40
        strat_cfg.tp1_r = 1.5
        strat_cfg.tp2_r = 2.0
        strat_cfg.max_loss_streak = 3
        strat_cfg.cooldown_bars = 48  # P0: 熔断后冷却 48 根 15m K 线 (12h) 自动解封
        strat_cfg.max_pending_bars = 3  # 3根K线内未成交则自动撤单
        strat_cfg.use_market_order = False  # 使用限价单挂单，并在3根K线未成交时撤单

        strategy = SMCLiveStrategy(strat_cfg)
        node.add_strategy(strategy)
        logger.info(f"Registered {coin} strategy (Tag: {tag}, ct_val: {ct_val}, max_pending_bars=3, use_hyphens=False)")

    logger.info(
        f"Leverage bootstrap: {leverage_ok}/{len(portfolio_matrix)} instruments confirmed at "
        f"{TARGET_LEVERAGE}x ({TARGET_MGN_MODE} margin)."
    )
    logger.info("All 4 assets registered successfully. Starting live multi-asset event loop...")
    node.run()


if __name__ == "__main__":
    main()
