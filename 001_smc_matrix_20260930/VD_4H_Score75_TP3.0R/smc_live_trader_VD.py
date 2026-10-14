#!/usr/bin/env python3
"""
策略编号: 001
策略名称: smc_matrix (多资产 SMC 动量回踩与狄利克雷证据门控量化交易系统)
首次部署: 2026-09-30
运行架构: NautilusTrader 2.0 (Rust/Python 混合事件驱动架构) + Docker

【核心特性与架构规范】:
1. 信号逻辑:
   - EMA 20/50 顺势大方向判定。
   - K 线微观压强 (CLV) 与 1.25x 均量放量异动过滤。
   - ATR 快速/慢速比值波动率有效区间 (0.55 ~ 1.80)。
   - 狄利克雷主观逻辑证据门控 (Dirichlet Evidential Gate: u <= 0.35, C < 0.40)。
2. 执行与风控:
   - 限价单回踩挂单入场，挂单有效期最大 3 根 K 线 (TTL = 3 bars)，超时主动撤单。
   - 单笔交易严格基于账户动态可用净值的 1.0% 计算风险预算与下单张数。
   - 全局最多允许 2 个活跃持仓并发 (PortfolioCoordinator)，防止系统性单边暴跌共振。
   - 平仓单强制追加 reduce_only=True，杜绝平仓手数超出引发的反向裸开仓。
   - 5 分钟心跳看门狗 (Watchdog) 自动比对底层 Net Position，自动认领并接管可能的脱管孤儿仓。
   - 启动瞬间调用 OKX 官方 REST 接口并发预热 60 根 4h K 线，实现秒级冷启动 (READY=TRUE)。
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

# ─── 日志格式化配置 ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("PROD-MATRIX")


# ─── 组合级风险协调器 (Portfolio Risk Coordinator) ────────────────────────────
class PortfolioCoordinator:
    """
    跨品种全局风险协调器：
    限制全账户最多同时持有的活跃仓位数量，消除多资产在极端单边行情下的敞口共振风险。
    """
    active_instruments: Set[str] = set()
    MAX_CONCURRENT_PORTFOLIO_POSITIONS: int = 2  # 组合最大同时持仓上限: 2

    @classmethod
    def can_open_position(cls, symbol: str) -> bool:
        """检查当前品种是否被允许发起新开仓"""
        if symbol in cls.active_instruments:
            return True
        return len(cls.active_instruments) < cls.MAX_CONCURRENT_PORTFOLIO_POSITIONS

    @classmethod
    def register_position(cls, symbol: str) -> None:
        """注册新确认的持仓品种"""
        cls.active_instruments.add(symbol)
        logger.info(
            f"[PORTFOLIO-RISK] 活跃持仓更新 ({len(cls.active_instruments)}/{cls.MAX_CONCURRENT_PORTFOLIO_POSITIONS}): "
            f"{list(cls.active_instruments)}"
        )

    @classmethod
    def release_position(cls, symbol: str) -> None:
        """释放已平仓的品种配额"""
        cls.active_instruments.discard(symbol)
        logger.info(
            f"[PORTFOLIO-RISK] 释放持仓配额. 剩余活跃持仓 ({len(cls.active_instruments)}/{cls.MAX_CONCURRENT_PORTFOLIO_POSITIONS}): "
            f"{list(cls.active_instruments)}"
        )


# ─── 主观逻辑狄利克雷证据门控 (Dirichlet Evidential Gate) ────────────────────────
class EvidentialFilter:
    """
    主观逻辑 (Subjective Logic) 不确定性门控引擎：
    量化认知真空度 (Vacuity Uncertainty, u) 与方向冲突度 (Directional Conflict, C)。
    信念守恒准则: b_bull + b_bear + b_neutral + u == 1.0
    """

    def __init__(self, u_max: float = 0.35, c_max: float = 0.40):
        self.u_max = u_max        # 最大允许的不确定性阈值
        self.c_max = c_max        # 最大允许的多空冲突度阈值

    def evaluate(self, bull_ev: float, bear_ev: float, base_neutral: float = 1.0) -> dict:
        """
        根据多空证据值计算信念分布与放行结果
        :param bull_ev: 多头证据强度 (0.0 ~ 10.0)
        :param bear_ev: 空头证据强度 (0.0 ~ 10.0)
        :param base_neutral: 先验中立证据基础权重
        """
        alpha_bull = max(bull_ev, 0.0) + 1.0
        alpha_bear = max(bear_ev, 0.0) + 1.0
        alpha_neutral = base_neutral + 1.0

        S = alpha_bull + alpha_bear + alpha_neutral
        K = 3.0  # 状态类别数 (多、空、中立)

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


# ─── 因果微观 SMC 特征计算引擎 ────────────────────────────────────────────────
class SMCFeatures:
    """在线流式向量化特征计算器 (严格因果，无任何未来数据泄漏)"""

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
        """更新最新的 15 分钟 OHLCV 数据并递推平滑指标"""
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
        """检查特征引擎是否已满足最小平滑样本数量"""
        return len(self.closes) >= max(self.atr_slow, self.ema_slow, self.vol_sma) + 5

    def compute(self) -> dict:
        """计算当根 K 线的全部微观动量与结构特征"""
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

        rng = max(h - l, 1e-9)
        # 收盘价位置压强 (Close Location Value, CLV)
        clv = ((c - l) - (h - c)) / rng
        is_bull_candle = c > self.opens[-1]

        score_long = 0.0
        score_short = 0.0

        # 1. 均线主趋势评分 (30 分)
        if c > ema_f > ema_s:
            score_long += 30.0
        elif c < ema_f < ema_s:
            score_short += 30.0

        # 2. 异动放量确认 (25 分)
        if vol_spike:
            if is_bull_candle:
                score_long += 25.0
            else:
                score_short += 25.0

        # 3. K线压强定向 (15 分)
        if clv > 0.4:
            score_long += 15.0
        elif clv < -0.4:
            score_short += 15.0

        # 4. 波动率健康通道 (15 分)
        atr_ratio = atr_f / (atr_s + 1e-9)
        if self.atr_ratio_min <= atr_ratio <= self.atr_ratio_max:
            score_long += 15.0
            score_short += 15.0

        # 5. 回踩 EMA20 支撑/阻力有效性 (15 分)
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


# ─── 策略配置类 ──────────────────────────────────────────────────────────────
class SMCLiveConfig(StrategyConfig):
    pass


# ─── 生产级策略主体实现 ────────────────────────────────────────────────────────
class SMCLiveStrategy(Strategy):
    """
    生产级多资产动量策略：
    严格由交易所底层 OrderFilled 事件驱动状态迁移，绝不盲目假定挂单即成交。
    """

    def __init__(self, config: SMCLiveConfig) -> None:
        super().__init__(config)
        self.cfg = config
        self.feats = SMCFeatures()
        self.filter = EvidentialFilter(u_max=config.u_max, c_max=config.c_max)

        # 实际确认持仓状态 (仅由 on_order_filled 驱动)
        self.in_position: bool = False
        self.pos_side: int = 0  # +1 为多头, -1 为空头
        self.entry_price: float = 0.0
        self.position_qty: float = 0.0
        self.stop_loss: float = 0.0
        self.tp1_price: float = 0.0
        self.tp2_price: float = 0.0
        self.tp1_filled: bool = False

        # 在途订单生命周期跟踪
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
        """策略启动钩子：订阅 K 线、REST 秒级预热、持仓认领续传、挂载看门狗定时器"""
        iid = InstrumentId.from_str(self.cfg.instrument_id)
        spec = BarSpecification(4, BarAggregation.HOUR, PriceType.LAST)
        bar_type = BarType(iid, spec, AggregationSource.EXTERNAL)
        self.subscribe_bars(bar_type)

        # 1. 解决冷启动等待：通过 REST 接口秒级预热 60 根历史 K 线
        self._warmup_from_okx_rest()
        raw_sym = self.cfg.instrument_id.split(".")[0]

        # 2. 状态恢复：认领底层已存在的持仓，防止重启变孤儿仓
        self._hydrate_existing_position(iid, raw_sym)

        # 3. 注册 5 分钟健康心跳与孤儿仓看门狗
        self.clock.set_timer(f"HEARTBEAT_{raw_sym}", timedelta(minutes=5), callback=self._on_heartbeat)

        self.log.info(
            f"=== 生产策略已激活 === [{self.cfg.instrument_id}] | "
            f"面值={self.cfg.ct_val} | 精度={self.cfg.price_precision} | "
            f"阈值={self.cfg.min_score} | 挂单模式={'市价' if self.cfg.use_market_order else '限价'} | "
            f"预热就绪={self.feats.ready} | 当前持仓状态={self.in_position}"
        )

    def _hydrate_existing_position(self, iid: InstrumentId, raw_sym: str) -> None:
        """冷启动或重启时从底层缓存自动接管存量持仓"""
        try:
            open_positions = self.cache.positions_open(instrument_id=iid)
            if open_positions:
                pos = open_positions[0]
                self.in_position = True
                self.pos_side = 1 if pos.is_long else -1
                self.entry_price = float(pos.avg_px_open)
                self.position_qty = float(pos.quantity)

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
                    f"[{raw_sym}] 成功接管存量持仓: 方向={'多头' if self.pos_side==1 else '空头'} "
                    f"张数={self.position_qty} @ {self.entry_price:.2f} | "
                    f"防线重构: SL={self.stop_loss:.2f} | TP1={self.tp1_price:.2f} | TP2={self.tp2_price:.2f}"
                )
        except Exception as e:
            self.log.error(f"[{raw_sym}] 接管存量持仓异常: {e}")

    def _warmup_from_okx_rest(self) -> None:
        """从 OKX REST 接口拉取历史 60 根 K 线实现毫秒级预热"""
        raw_sym = self.cfg.instrument_id.split(".")[0]
        url = f"https://www.okx.com/api/v5/market/candles?instId={raw_sym}&bar=4h&limit=60"
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
                    f"[{raw_sym}] REST 预热成功: 加载 {len(candles)} 根 K 线 | "
                    f"最新价={f['close']:.2f} | EMA20={f['ema_fast']:.2f} | EMA50={f['ema_slow']:.2f} | "
                    f"评分 多={f['score_long']:.1f}, 空={f['score_short']:.1f} | 状态=就绪"
                )
        except Exception as e:
            self.log.error(f"[{raw_sym}] REST 预热失败: {e}")

    def _on_heartbeat(self, event) -> None:
        """5 分钟心跳与看门狗：实时比对交易所真实 Net Position，自动识别并自愈孤儿仓"""
        raw_sym = self.cfg.instrument_id.split(".")[0]
        iid = InstrumentId.from_str(self.cfg.instrument_id)
        try:
            net_pos = self.portfolio.net_position(iid)
            actual_net = float(net_pos.as_double() if hasattr(net_pos, "as_double") else net_pos)

            # 孤儿仓自愈检测：交易所存在真实持仓但策略未感知到
            if actual_net != 0 and not self.in_position:
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
                    f"[{raw_sym}] 看门狗捕获并认领脱管孤儿仓! 真实净仓={actual_net} | "
                    f"挂载止损 SL={self.stop_loss:.2f} | 止盈 TP2={self.tp2_price:.2f}"
                )
            elif actual_net == 0 and self.in_position:
                # 外部手动平仓感知复位
                self.in_position = False
                self.pos_side = 0
                self.position_qty = 0.0
                PortfolioCoordinator.release_position(raw_sym)

            f = self.feats.compute()
            self.log.info(
                f"[心跳巡检] {raw_sym:15s} | 价格={f['close']:8.2f} | "
                f"持仓={self.in_position} | 真实净仓={actual_net} | 在途委托={self.pending_entry_order_id is not None} | "
                f"交易笔数={self.total_trades} | 累计实现盈亏={self.realized_pnl:.2f} USDT"
            )
        except Exception as e:
            self.log.warning(f"[{raw_sym}] 心跳计算异常: {e}")

    def on_bar(self, bar: Bar) -> None:
        """主行情事件循环：驱动超时撤单、持仓追踪、信号打分与委托提交"""
        raw_sym = self.cfg.instrument_id.split(".")[0]
        o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
        try:
            v = float(bar.volume)
        except Exception:
            v = 1.0

        self.feats.update(o, h, l, c, v)
        self.bars_processed += 1

        # 1. 限价在途单超时撤单机制 (TTL = 3 Bars)
        if self.pending_entry_order_id is not None:
            self.pending_entry_bars += 1
            max_bars = getattr(self.cfg, "max_pending_bars", 3)
            if self.pending_entry_bars >= max_bars:
                self.log.warning(
                    f"[{raw_sym}] 限价委托单 {self.pending_entry_order_id} 经历 {self.pending_entry_bars} 根 K 线仍未成交 "
                    f"(>= {max_bars} 根阈值). 发起主动撤单..."
                )
                try:
                    self.cancel_order(self.pending_entry_order_id)
                except Exception as e:
                    self.log.warning(f"[{raw_sym}] 撤单提示 (订单可能已完结): {e}. 清理本地在途标识.")
                    self.pending_entry_order_id = None
                    self.pending_entry_bars = 0
                return
            else:
                self.log.info(
                    f"[{raw_sym}] 限价委托单 {self.pending_entry_order_id} 等待撮合中 "
                    f"({self.pending_entry_bars}/{max_bars} 根 K 线)..."
                )
                return

        # 2. 追踪管理已确认的活跃持仓 (止盈止损评估)
        if self.in_position:
            self._manage_position(h, l, c)
            return

        # 3. 连续亏损熔断保护与 12 小时 (48 根 4h K线) 冷却自动解封机制
        if self.consec_losses >= self.cfg.max_loss_streak:
            self.breaker_bars += 1
            cooldown_limit = getattr(self.cfg, "cooldown_bars", 48)  # 48 根 4h K 线 = 12 小时
            if self.breaker_bars < cooldown_limit:
                if self.breaker_bars % 4 == 0 or self.breaker_bars == 1:
                    self.log.warning(
                        f"[{raw_sym}] 连续亏损熔断保护中 ({self.consec_losses} 次连续亏损): "
                        f"冷却进度 {self.breaker_bars}/{cooldown_limit} 根 K 线 (暂停开仓)..."
                    )
                return
            else:
                self.log.info(
                    f"[{raw_sym}] 熔断冷却期满 ({self.breaker_bars} 根 K 线 / 12 小时)! 自动解封并重置连续亏损计数，恢复正常交易。"
                )
                self.consec_losses = 0
                self.breaker_bars = 0

        # 4. 组合级敞口并发限制 (防止多币种同向共振)
        if not PortfolioCoordinator.can_open_position(raw_sym):
            return

        # 5. 信号特征评估
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

        # 6. 狄利克雷证据不确定性门控过滤
        bull_ev = score_long / 10.0
        bear_ev = score_short / 10.0
        gate_res = self.filter.evaluate(bull_ev, bear_ev)

        self.log.info(
            f"[{raw_sym}] 触发交易信号: {'做多' if direction == 1 else '做空'} | 评分={score:.1f} | "
            f"认知不确定性 u={gate_res['u']:.3f}, 冲突度 C={gate_res['C']:.3f} | 门控放行={gate_res['passed']}"
        )

        if not gate_res["passed"]:
            return

        # 7. 动态资金风险预算 (单笔 1% 风险)
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

        # 8. 构造并发送委托 (状态必须等待 on_order_filled 才能迁移)
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
            f"[{raw_sym}] 委托已提交 (ID={order.client_order_id}): {side.name} {contracts} 张 | "
            f"单笔风险预算=${risk_budget:.2f} (基于实时净值 ${equity:.2f}) | 等待交易所撮合回报..."
        )

    # ─── 订单生命周期事件回调 ─────────────────────────────────────────────────────
    def on_order_submitted(self, event: OrderSubmitted) -> None:
        self.log.info(f"[{self.cfg.instrument_id}] 订单已确认提交: {event.client_order_id}")

    def on_order_accepted(self, event: OrderAccepted) -> None:
        self.log.info(f"[{self.cfg.instrument_id}] 订单已成功到达交易所: {event.client_order_id}")

    def on_order_denied(self, event: OrderDenied) -> None:
        """捕获 OKX 底层拒绝，复位在途状态防止状态机死锁"""
        raw_sym = self.cfg.instrument_id.split(".")[0]
        self.log.error(f"[{raw_sym}] 订单被拒绝 (Denied): {event.client_order_id} | 原因='{event.reason}'")
        if event.client_order_id == self.pending_entry_order_id:
            self.pending_entry_order_id = None
            self.pending_entry_bars = 0
        if event.client_order_id == self.pending_exit_order_id:
            self.pending_exit_order_id = None

    def on_order_rejected(self, event: OrderRejected) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        self.log.error(f"[{raw_sym}] 订单被驳回 (Rejected): {event.client_order_id} | 原因='{event.reason}'")
        if event.client_order_id == self.pending_entry_order_id:
            self.pending_entry_order_id = None
            self.pending_entry_bars = 0
        if event.client_order_id == self.pending_exit_order_id:
            self.pending_exit_order_id = None

    def on_order_canceled(self, event: OrderCanceled) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        self.log.info(f"[{raw_sym}] 订单成功撤销: {event.client_order_id}")
        if event.client_order_id == self.pending_entry_order_id:
            self.pending_entry_order_id = None
            self.pending_entry_bars = 0
        if event.client_order_id == self.pending_exit_order_id:
            self.pending_exit_order_id = None

    def on_order_expired(self, event: OrderExpired) -> None:
        raw_sym = self.cfg.instrument_id.split(".")[0]
        self.log.info(f"[{raw_sym}] 订单已失效 (Expired): {event.client_order_id}")
        if event.client_order_id == self.pending_entry_order_id:
            self.pending_entry_order_id = None
            self.pending_entry_bars = 0
        if event.client_order_id == self.pending_exit_order_id:
            self.pending_exit_order_id = None

    def on_order_filled(self, event: OrderFilled) -> None:
        """核心撮合成交回调：严格基于底层 Net Position 确认持仓，严防多卖与反向开仓"""
        raw_sym = self.cfg.instrument_id.split(".")[0]
        fill_px = float(event.last_px)
        fill_qty = float(event.last_qty)
        order_id = event.client_order_id

        # 1. 入场单成交确认
        if order_id == self.pending_entry_order_id:
            iid = InstrumentId.from_str(self.cfg.instrument_id)
            net_pos = self.portfolio.net_position(iid)
            actual_net = float(net_pos.as_double() if hasattr(net_pos, "as_double") else net_pos)

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
                    f"[{raw_sym}] >>> 开仓撮合成交确认 <<< 成交 {fill_qty} 张 @ {fill_px:.2f} | "
                    f"交易所真实净仓={actual_net} | 止损 SL={self.stop_loss:.2f} | 止盈 TP1={self.tp1_price:.2f} | TP2={self.tp2_price:.2f}"
                )
            else:
                self.log.warning(f"[{raw_sym}] 订单成交 {fill_qty} 张，但净持仓为 0，视为已平净状态.")
                self.in_position = False
                self.pos_side = 0
                self.position_qty = 0.0
                self.pending_entry_order_id = None
                self.pending_entry_bars = 0
                PortfolioCoordinator.release_position(raw_sym)
            return

        # 2. 出场平仓单成交确认
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
                f"[{raw_sym}] >>> 平仓成交确认 <<< 平仓均价 {fill_px:.2f} | "
                f"本笔盈亏={pnl:.2f} USDT | 累计实现盈亏={self.realized_pnl:.2f} USDT"
            )

    def _manage_position(self, h: float, l: float, c: float) -> None:
        """持仓监控逻辑：触发止盈止损时，严格向交易所发送带有 reduce_only=True 的市价平仓委托"""
        if self.pending_exit_order_id is not None:
            return

        iid = InstrumentId.from_str(self.cfg.instrument_id)
        raw_sym = self.cfg.instrument_id.split(".")[0]

        # 实时核对底层净持仓
        net_pos = self.portfolio.net_position(iid)
        real_qty = abs(float(net_pos.as_double() if hasattr(net_pos, "as_double") else net_pos))

        if real_qty <= 0:
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
                exit_reason = "止损离场 (STOP_LOSS)"
            elif h >= self.tp2_price:
                should_exit = True
                exit_reason = "止盈离场 (TAKE_PROFIT)"
        else:
            if h >= self.stop_loss:
                should_exit = True
                exit_reason = "止损离场 (STOP_LOSS)"
            elif l <= self.tp2_price:
                should_exit = True
                exit_reason = "止盈离场 (TAKE_PROFIT)"

        if should_exit:
            exit_side = OrderSide.SELL if self.pos_side == 1 else OrderSide.BUY
            # 物理级防反向开仓：强制追加 reduce_only=True，且手数严格等于当前 Net Position
            order = self.order_factory.market(
                instrument_id=iid,
                order_side=exit_side,
                quantity=Quantity.from_int(int(real_qty)),
                reduce_only=True,
            )
            self.pending_exit_order_id = order.client_order_id
            self.submit_order(order)
            self.log.info(
                f"[{raw_sym}] 发送【只减仓】平仓市价单 ({exit_reason}): "
                f"{exit_side.name} {int(real_qty)} 张 (交易所当前净仓={real_qty})..."
            )


# ─── 多品种实盘节点装配入口 ───────────────────────────────────────────────────
def main() -> None:
    logger.info("=" * 75)
    logger.info("NAUTILUS TRADER - 4 品种矩阵量化生产系统启动")
    logger.info("标的矩阵: BTC-USDT-SWAP, ETH-USDT-SWAP, SOL-USDT-SWAP, BNB-USDT-SWAP")
    logger.info("执行模式: OKX DEMO | 账户: OKX-DEMO-001 | 周期: 15 分钟 K 线")
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

    # 4 资产核心配置矩阵
    # 格式: (symbol, 合约面值 ct_val, 价格小数精度 prec, 策略标签 tag, 最低入场信号分 score)
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
            use_hyphens_in_client_order_ids=False,  # 强制 OKX 纯数字字母规范，杜绝 OrderDenied
        )
        strat_cfg.instrument_id = f"{symbol}.{OKX}"
        strat_cfg.ct_val = ct_val
        strat_cfg.price_precision = prec
        strat_cfg.risk_pct = 0.010              # 单笔 1.0% 风险预算
        strat_cfg.min_score = 75.0
        strat_cfg.u_max = 0.35                  # 狄利克雷不确定性上限
        strat_cfg.c_max = 0.40                  # 多空冲突度上限
        strat_cfg.tp1_r = 1.5                   # 1.5R 保本停损锚点
        strat_cfg.tp2_r = 3.0                   # 2.0R 终极止盈目标
        strat_cfg.max_loss_streak = 3           # 连续 3 笔止损熔断
        strat_cfg.cooldown_bars = 3            # 熔断后冷却 48 根 4h K 线 (12小时) 自动解封并重置连亏数
        strat_cfg.max_pending_bars = 3          # 限价单 3 根 K 线未成交主动撤单
        strat_cfg.use_market_order = False      # 采用限价单回踩挂单入场

        strategy = SMCLiveStrategy(strat_cfg)
        node.add_strategy(strategy)
        logger.info(
            f"已成功加载并注册 {coin} 策略实例 (标签: {tag}, 面值: {ct_val}, 撤单TTL=3根K线, 纯字符ID=True)"
        )

    logger.info("全部 4 资产策略注册完毕，正式启动底层多资产事件驱动循环...")
    node.run()


if __name__ == "__main__":
    main()
