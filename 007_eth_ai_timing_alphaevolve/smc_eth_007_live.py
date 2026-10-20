#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""007 ETH AI 择时 (AlphaEvolve GP + Q-State 15m) —— OKX 永续执行器

信号规格逐条对齐本目录下的 Pine 脚本 ETH_AI_Timing_AlphaEvolve_15m.pine：

    q_val  = 0.88 * q_val[-1] + 0.12 * (k_pos * 15.0 + hl_spread * 0.8)
    partA  = (close - SMA20(close)) / STDEV20(close)      # Pine ta.stdev 默认 biased=true，即总体标准差
    signal = partA + 0.3   if q_val >  0.05
             partA - 0.3   if q_val < -0.05
             partA         其它
    开多: signal > +1.20        开空: signal < -1.20
    首仓: 可用现金 50% 的名义价值   加仓: 剩余现金 75% 的名义价值
    止盈: +0.90% (相对持仓均价)     止损: -2.50% (相对持仓均价)

与仓库原 nautilus_eth_strategy_15m.py 的差异：原文件只是 55 行桩代码——交易对写的是
BINANCE、只有 self.log.info 从不下单、且没有止盈止损。本文件是真正可执行的实现，
状态机只在 on_order_filled 里确认（不假设成交）。

运行环境：nautilus_trader 2.0.0rc6 + Python 3.13（与 /root/nautilus2-venv 一致）。
凭证：OKX_API_KEY / OKX_API_SECRET / OKX_API_PASSPHRASE，OKX_ENV=DEMO|LIVE。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import math
import os
import urllib.request
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

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
from nautilus_trader.common import Environment, LoggerConfig, LogLevel
from nautilus_trader.config import StrategyConfig
from nautilus_trader.live import LiveNode, LiveRiskEngineConfig
from nautilus_trader.model import (
    AccountId,
    AggregationSource,
    Bar,
    BarAggregation,
    BarSpecification,
    BarType,
    ClientOrderId,
    InstrumentId,
    OrderCanceled,
    OrderDenied,
    OrderExpired,
    OrderFilled,
    OrderRejected,
    OrderSide,
    PriceType,
    Quantity,
    StrategyId,
    TraderId,
)
from nautilus_trader.trading import Strategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AE007")

# ─── 运行参数（环境变量可覆盖，默认走模拟盘） ─────────────────────────────────
SYMBOL = os.getenv("AE_SYMBOL", "ETH-USDT-SWAP")
LEVERAGE = int(os.getenv("AE_LEVERAGE", "10"))
MGN_MODE = os.getenv("AE_MGN_MODE", "cross").lower()          # OKX REST 用小写 cross/isolated
OKX_ACCOUNT_ID = os.getenv("OKX_ACCOUNT_ID", "OKX-007-001")
OKX_ENV = os.getenv("OKX_ENV", "DEMO").strip().upper()
IS_LIVE = OKX_ENV == "LIVE"

# ─── 策略参数（与 Pine 脚本 input 默认值逐项一致） ─────────────────────────────
GAMMA = 0.88          # Q-State 折扣因子
ALPHA = 0.12          # TD 状态学习率
THRESH = 1.20         # 开仓信号极值阈值
TP_PCT = 0.0090       # 动态追踪止盈 0.90%
SL_PCT = 0.0250       # 硬性截断止损 2.50%
FIRST_RATIO = 0.50    # 首仓占可用现金比例
ADD_RATIO = 0.75      # 加仓占剩余现金比例
LOOKBACK = 20         # SMA/STDEV 窗口

# ─── 安全阀 ───────────────────────────────────────────────────────────────────
MAX_SL_STREAK = 3              # 连续 3 笔硬止损 → 熔断
HALT_HOURS = 48                # 熔断冷却 48 小时（对齐 README L3 条款）
FEED_STALE_ENTRY_SEC = 20 * 60  # 行情超 20 分钟不更新 → 禁止开新仓
FEED_STALE_FLATTEN_SEC = 30 * 60  # 持仓中行情超 30 分钟不更新 → 市价强平
WARMUP_BARS = 100             # 启动时从 OKX REST 回补的 15m K 线数量

OKX_REST_BASE = "https://www.okx.com"
OKX_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# ─── OKX REST 辅助（签名 / 公共行情） ─────────────────────────────────────────
def _now_ms() -> int:
    """当前时间（毫秒）。实盘＝墙钟；离线回测时由测试脚本替换为模拟时钟。"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def okx_signed(method: str, path: str, body_obj: Optional[dict] = None) -> Optional[dict]:
    """OKX 私有接口签名请求。凭证缺失或网络异常返回 None（不抛异常）。"""
    api_key = os.getenv("OKX_API_KEY", "")
    api_secret = os.getenv("OKX_API_SECRET", "")
    passphrase = os.getenv("OKX_API_PASSPHRASE", "")
    if not (api_key and api_secret and passphrase):
        return None
    body = json.dumps(body_obj) if body_obj is not None else ""
    ts = _utc_ts()
    prehash = f"{ts}{method}{path}{body}"
    sign = base64.b64encode(
        hmac.new(api_secret.encode(), prehash.encode(), hashlib.sha256).digest()
    ).decode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": OKX_UA,
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": passphrase,
    }
    if not IS_LIVE:
        headers["x-simulated-trading"] = "1"
    req = urllib.request.Request(
        OKX_REST_BASE + path,
        data=body.encode() if body else None,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001 - 启动期网络问题不应让进程崩溃
        logger.warning(f"[REST] {method} {path} 失败: {exc}")
        return None


def okx_public(path: str) -> Optional[dict]:
    req = urllib.request.Request(OKX_REST_BASE + path, headers={"User-Agent": OKX_UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[REST] 公共接口 {path} 失败: {exc}")
        return None


def set_okx_leverage(symbol: str, leverage: int, mgn_mode: str) -> bool:
    """设置账户杠杆（OKX 侧持久化）。失败仅告警：本策略名义价值 ≤87.5% 权益，1x 以上均可跑。"""
    body = {"instId": symbol, "lever": str(leverage), "mgnMode": mgn_mode}
    resp = okx_signed("POST", "/api/v5/account/set-leverage", body)
    if resp is None:
        logger.error(f"[{symbol}] 设置 {leverage}x 杠杆失败：凭证缺失或请求异常")
        return False
    if resp.get("code") == "0":
        logger.info(f"[{symbol}] 杠杆已确认: {leverage}x | mgnMode={mgn_mode}")
        return True
    logger.error(
        f"[{symbol}] 设置杠杆被拒: code={resp.get('code')} msg={resp.get('msg')} "
        f"(mgnMode={mgn_mode} 需与账户持仓模式一致)"
    )
    return False


# ─── 信号层（纯计算，无 nautilus 依赖，可离线逐根回放校验） ────────────────────
class AlphaEvolveSignal:
    """Pine 脚本的 Q-State + 价格 Z-Score 合成信号。每根 15m 收盘 K 线调用一次 update()。"""

    def __init__(self) -> None:
        self.closes: deque[float] = deque(maxlen=LOOKBACK)
        self.q_val = 0.0
        self.value: Optional[float] = None
        self.bars = 0

    def update(self, o: float, h: float, l: float, c: float) -> Optional[float]:
        hl_range = h - l
        k_pos = (c - l) / (hl_range + 1e-6)
        hl_spread = hl_range / (c + 1e-6)

        # 1. 涌现 Q-State 状态价值迭代（递归依赖上一根，故必须先算）
        self.q_val = GAMMA * self.q_val + ALPHA * (k_pos * 15.0 + hl_spread * 0.8)

        # 2. 价格 Z-Score + Q-State 共振加成
        self.closes.append(c)
        self.bars += 1
        if len(self.closes) < LOOKBACK:
            self.value = None
            return None
        n = len(self.closes)
        mean = sum(self.closes) / n
        var = sum((x - mean) ** 2 for x in self.closes) / n  # 总体方差（Pine biased=true）
        sd = math.sqrt(var)
        part_a = (c - mean) / sd if sd > 0 else 0.0
        if self.q_val > 0.05:
            part_a += 0.3
        elif self.q_val < -0.05:
            part_a -= 0.3
        self.value = part_a
        return self.value


# ─── Nautilus 策略配置（字段在 main() 里按 OKX 合约规格注入） ──────────────────
class AlphaEvolveConfig(StrategyConfig):
    pass


# ─── 执行层 ───────────────────────────────────────────────────────────────────
class AlphaEvolveEthStrategy(Strategy):
    """ETH 15m 单标的执行器：15m 收盘出信号、1m K 线巡检止盈止损、成交回报驱动状态机。"""

    def __init__(self, config: AlphaEvolveConfig) -> None:
        super().__init__(config)
        self.cfg = config
        self.sig = AlphaEvolveSignal()
        self.iid = InstrumentId.from_str(config.instrument_id)
        self.bar_type_15m = BarType(
            self.iid, BarSpecification(15, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL
        )
        self.bar_type_1m = BarType(
            self.iid, BarSpecification(1, BarAggregation.MINUTE, PriceType.LAST), AggregationSource.EXTERNAL
        )

        # 合约规格（启动时用 OKX 公共接口覆盖）
        self.ct_val = 0.10
        self.size_prec = 2

        # 持仓状态：只在 on_order_filled 之后变更
        self.in_position = False
        self.pos_side = 0
        self.pos_contracts = 0.0
        self.pos_units = 0.0
        self.open_notional = 0.0
        self.entry_avg = 0.0
        self.entry_fee = 0.0
        self.exit_fee = 0.0
        self.exit_proceeds = 0.0
        self.exit_contracts = 0.0
        self.exit_reason = ""
        self.order_step = 0

        # 在途委托
        self.pending_kind: Optional[str] = None  # entry / add / exit
        self.pending_order_id: Optional[ClientOrderId] = None
        self.pending_side = 0
        self.last_entry_oid: Optional[ClientOrderId] = None
        self.last_exit_oid: Optional[ClientOrderId] = None

        # 资金与统计
        self.cash = 0.0
        self.start_cash = 0.0
        self.realized_pnl = 0.0
        self.trades = 0
        self.wins = 0
        self.sl_streak = 0
        self.halt_until: Optional[datetime] = None

        # 行情新鲜度
        self.last_px = 0.0
        self.last_bar_ms = 0
        self.last_15m_ts = 0
        self.last_1m_ts = 0
        self.bars_15m = 0
        self.bars_1m = 0
        self.started_ms = 0

    # ── 生命周期 ──────────────────────────────────────────────────────────────
    def on_start(self) -> None:
        self.started_ms = _now_ms()
        self.subscribe_bars(self.bar_type_15m)
        self.subscribe_bars(self.bar_type_1m)

        self._load_contract_spec()
        self._warmup()
        self.cash = self._read_equity()
        self.start_cash = self.cash
        if self.cash <= 0:
            logger.error(
                "无法读取 USDT 账户权益 → 拒绝交易（不做任何 fallback 权益，缺数据就不下单）。"
                " 心跳会持续重试，读到权益后自动恢复。"
            )
        self._hydrate_position()
        self.clock.set_timer("AE007-HEARTBEAT", timedelta(minutes=5), callback=self._on_heartbeat)

        logger.info(
            f"=== 007 ETH AlphaEvolve 执行器已启动 === {self.cfg.instrument_id} | "
            f"env={'LIVE' if IS_LIVE else 'DEMO'} | ctVal={self.ct_val} | size_prec={self.size_prec} | "
            f"权益={self.cash:.2f} USDT | signal={self.sig.value} | InPos={self.in_position}"
        )

    def on_stop(self) -> None:
        if self.in_position:
            logger.error(
                f"!!! 进程停止时仍持有 {self.pos_side:+d} 方向 {self.pos_contracts} 张 "
                f"(均价 {self.entry_avg:.2f}) —— 软件止盈止损已失效，请在 OKX 手动处理 !!!"
            )
        logger.info(
            f"=== 停止 === 已平仓 {self.trades} 笔 | 胜 {self.wins} | "
            f"实现盈亏 {self.realized_pnl:+.2f} USDT | 现金 {self.cash:.2f} USDT"
        )

    # ── 启动期：合约规格 / 历史回补 / 权益 / 持仓接管 ─────────────────────────
    def _load_contract_spec(self) -> None:
        resp = okx_public(f"/api/v5/public/instruments?instType=SWAP&instId={SYMBOL}")
        try:
            row = resp["data"][0]
            self.ct_val = float(row["ctVal"])
            self.size_prec = max(0, -int(round(math.log10(float(row["lotSz"])))))
            logger.info(
                f"[SPEC] {SYMBOL}: ctVal={self.ct_val} lotSz={row['lotSz']} tickSz={row['tickSz']} "
                f"minSz={row['minSz']} → size_prec={self.size_prec}"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[SPEC] 读取合约规格失败({exc})，回退 ETH ctVal={self.ct_val} size_prec={self.size_prec}")

    def _warmup(self) -> None:
        resp = okx_public(f"/api/v5/market/candles?instId={SYMBOL}&bar=15m&limit={WARMUP_BARS}")
        try:
            rows = list(reversed(resp["data"]))
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[WARMUP] 历史 K 线回补失败: {exc} —— 需积累 20 根 15m K 线后才会出信号")
            return
        fed = 0
        for row in rows:
            if row[8] != "1":  # 未收盘的 K 线不回放
                continue
            self.sig.update(float(row[1]), float(row[2]), float(row[3]), float(row[4]))
            self.last_px = float(row[4])
            fed += 1
        self.last_bar_ms = _now_ms()
        logger.info(
            f"[WARMUP] 回放 {fed} 根 15m K 线 | q_val={self.sig.q_val:+.4f} | "
            f"signal={self.sig.value} | 最新价={self.last_px:.2f}"
        )

    def _read_equity(self) -> float:
        """读取仓位计算基准资金。

        默认取 USDT 明细的 eq（结算币种口径）——策略的现金账本、盈亏、手续费全是 USDT，
        口径必须一致。totalEq 是跨币种折算总额（模似账户里除 USDT 外还有别的资产），
        拿它当仓位基数会把仓位放大十几倍，故仅在 AE_EQUITY_MODE=total 时使用。
        """
        resp = okx_signed("GET", "/api/v5/account/balance")
        if not (isinstance(resp, dict) and resp.get("code") == "0" and resp.get("data")):
            return 0.0
        acct = resp["data"][0]
        try:
            total_eq = float(acct.get("totalEq") or 0.0)
        except Exception:  # noqa: BLE001
            total_eq = 0.0
        mode = os.getenv("AE_EQUITY_MODE", "usdt").strip().lower()
        if mode == "total" and total_eq > 0:
            logger.info(f"[EQUITY] AE_EQUITY_MODE=total → 使用 totalEq={total_eq:.2f} USDT")
            return total_eq
        for detail in acct.get("details", []):
            if detail.get("ccy") == "USDT":
                try:
                    usdt_eq = float(detail.get("eq") or 0.0)
                except Exception:  # noqa: BLE001
                    usdt_eq = 0.0
                if usdt_eq > 0:
                    logger.info(
                        f"[EQUITY] USDT eq={usdt_eq:.2f}（仓位基数） | totalEq={total_eq:.2f}（跨币种总额，不参与计算）"
                    )
                    return usdt_eq
        if total_eq > 0:
            logger.warning(f"[EQUITY] 未找到 USDT 明细 → 退回 totalEq={total_eq:.2f}")
            return total_eq
        return 0.0

    def _hydrate_position(self) -> None:
        try:
            open_positions = self.cache.positions_open(instrument_id=self.iid)
            if not open_positions:
                logger.info("[HYDRATE] 启动检查：账户无遗留持仓")
                return
            pos = open_positions[0]
            self.in_position = True
            self.pos_side = 1 if pos.is_long else -1
            self.pos_contracts = float(pos.quantity)
            self.pos_units = self.pos_contracts * self.ct_val
            self.entry_avg = float(pos.avg_px_open)
            self.open_notional = self.pos_units * self.entry_avg
            self.order_step = 2  # 接管后只等止盈止损，不再加仓（避免把仓位越接越大）
            logger.warning(
                f"[HYDRATE] 接管遗留持仓: side={self.pos_side:+d} 张数={self.pos_contracts} "
                f"均价={self.entry_avg:.2f} → TP={self._tp_price():.2f} SL={self._sl_price():.2f} (不再加仓)"
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[HYDRATE] 接管持仓失败: {exc}")

    # ── 行情入口 ──────────────────────────────────────────────────────────────
    def on_bar(self, bar: Bar) -> None:
        if bar.bar_type == self.bar_type_1m:
            if bar.ts_event <= self.last_1m_ts:  # 回放/重复投递去重
                return
            self.last_1m_ts = bar.ts_event
            self.bars_1m += 1
            self.last_px = float(bar.close)
            if self.in_position and self.pending_kind != "exit":
                self._check_exit(float(bar.high), float(bar.low), "1m")
            return
        if bar.bar_type != self.bar_type_15m:
            return

        if bar.ts_event <= self.last_15m_ts:  # 回放/重复投递去重
            return
        self.last_15m_ts = bar.ts_event
        o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
        self.bars_15m += 1
        self.last_px = c
        self.last_bar_ms = bar.ts_event // 1_000_000
        signal = self.sig.update(o, h, l, c)

        # 出场优先（与 Pine 中 strategy.exit 每根 K 线重挂一致）
        if self.in_position and self.pending_kind != "exit":
            self._check_exit(h, l, "15m")
        if signal is None:
            return

        if self.in_position:
            if (
                self.order_step == 1
                and self.pending_order_id is None
                and abs(signal) > THRESH
                and self.pos_side == (1 if signal > 0 else -1)
            ):
                self._submit_entry(self.pos_side, ADD_RATIO, signal, kind="add")
            return

        if not self._entries_allowed():
            return
        if signal > THRESH:
            self._submit_entry(1, FIRST_RATIO, signal, kind="entry")
        elif signal < -THRESH:
            self._submit_entry(-1, FIRST_RATIO, signal, kind="entry")

    # ── 下单 ──────────────────────────────────────────────────────────────────
    def _entries_allowed(self) -> bool:
        if self.cash <= 0:
            return False
        if self.pending_order_id is not None:
            return False
        if self.halt_until is not None:
            if _now_ms() < int(self.halt_until.timestamp() * 1000):
                return False
            logger.warning(f"[L3] 熔断冷却到期（{self.halt_until.isoformat()}）→ 恢复开仓，连亏计数清零")
            self.halt_until = None
            self.sl_streak = 0
        stale_sec = (_now_ms() - self.last_bar_ms) / 1000.0
        if self.last_bar_ms and stale_sec > FEED_STALE_ENTRY_SEC:
            logger.warning(f"行情已 {stale_sec/60:.0f} 分钟未更新 → 暂不开新仓")
            return False
        if self.sig.value is None:
            return False
        return True

    def _submit_entry(self, side: int, ratio: float, signal: float, kind: str) -> None:
        if self.pending_order_id is not None or self.last_px <= 0:
            return
        available = self.cash - (self.open_notional if self.in_position else 0.0)
        if available <= 0:
            logger.warning(f"[{kind}] 可用现金 {available:.2f} ≤ 0 → 无法下单")
            return
        notional = available * ratio
        qty_contracts = notional / (self.ct_val * self.last_px)
        qty = math.floor(qty_contracts * (10 ** self.size_prec)) / (10 ** self.size_prec)
        if qty <= 0:
            logger.warning(
                f"[{kind}] 名义价值 {notional:.2f} USDT 折合 {qty_contracts:.4f} 张 < 最小 1 单位 → 跳过"
            )
            return
        order_side = OrderSide.BUY if side == 1 else OrderSide.SELL
        order = self.order_factory.market(
            instrument_id=self.iid,
            order_side=order_side,
            quantity=Quantity.from_str(f"{qty:.{self.size_prec}f}"),
        )
        self.pending_order_id = order.client_order_id
        self.pending_kind = kind
        self.pending_side = side
        self.order_step = 2 if kind == "add" else 1
        self.submit_order(order)
        logger.info(
            f"[{kind.upper()}] {'多' if side == 1 else '空'} @≈{self.last_px:.2f} | signal={signal:+.2f} | "
            f"名义={notional:.2f} USDT ({ratio*100:.0f}% of {available:.2f}) | {qty} 张 | id={order.client_order_id}"
        )

    def _tp_price(self) -> float:
        return self.entry_avg * (1 + TP_PCT) if self.pos_side == 1 else self.entry_avg * (1 - TP_PCT)

    def _sl_price(self) -> float:
        return self.entry_avg * (1 - SL_PCT) if self.pos_side == 1 else self.entry_avg * (1 + SL_PCT)

    def _check_exit(self, high: float, low: float, src: str) -> None:
        if not self.in_position or self.pos_contracts <= 0 or self.entry_avg <= 0:
            return
        if self.pending_order_id is not None:
            return
        tp = self._tp_price()
        sl = self._sl_price()
        if self.pos_side == 1:
            if high >= tp:
                self._submit_exit("TP", tp, src)
            elif low <= sl:
                self._submit_exit("SL", sl, src)
        else:
            if low <= tp:
                self._submit_exit("TP", tp, src)
            elif high >= sl:
                self._submit_exit("SL", sl, src)

    def _submit_exit(self, reason: str, trigger_px: float, src: str) -> None:
        if self.pending_order_id is not None or self.pos_contracts <= 0:
            return
        order_side = OrderSide.SELL if self.pos_side == 1 else OrderSide.BUY
        order = self.order_factory.market(
            instrument_id=self.iid,
            order_side=order_side,
            quantity=Quantity.from_str(f"{self.pos_contracts:.{self.size_prec}f}"),
            reduce_only=True,
        )
        self.pending_order_id = order.client_order_id
        self.pending_kind = "exit"
        self.exit_reason = reason
        self.submit_order(order)
        logger.info(
            f"[EXIT-{reason}] 触发价={trigger_px:.2f} ({src}) 最新价={self.last_px:.2f} | "
            f"平 {self.pos_side:+d} {self.pos_contracts} 张 (均价 {self.entry_avg:.2f}) | id={order.client_order_id}"
        )

    # ── 成交与委托生命周期 ────────────────────────────────────────────────────
    def _commission(self, event: OrderFilled) -> float:
        try:
            money = getattr(event, "commission", None)
            if money is None:
                return 0.0
            if str(getattr(money, "currency", "USDT")).upper() not in ("USDT", "USD"):
                return 0.0
            return float(money.as_double())
        except Exception:  # noqa: BLE001
            return 0.0

    @staticmethod
    def _num(value: object) -> float:
        try:
            return float(value.as_double()) if hasattr(value, "as_double") else float(value)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001
            return 0.0

    def _net_position(self) -> float:
        try:
            return self._num(self.portfolio.net_position(self.iid))
        except Exception:  # noqa: BLE001
            return 0.0

    def on_order_filled(self, event: OrderFilled) -> None:
        oid = event.client_order_id
        px = self._num(event.last_px)
        qty = self._num(event.last_qty)
        fee = self._commission(event)

        # 1) 开仓/加仓成交（含同一委托的后续部分成交）
        if oid == self.last_entry_oid or (oid == self.pending_order_id and self.pending_kind in ("entry", "add")):
            self.last_entry_oid = oid
            self.pos_side = self.pending_side if self.pending_side != 0 else self.pos_side
            self.in_position = True
            self.pos_contracts += qty
            self.pos_units = self.pos_contracts * self.ct_val
            self.open_notional += qty * self.ct_val * px
            self.entry_avg = self.open_notional / self.pos_units if self.pos_units > 0 else px
            self.entry_fee += fee
            if oid == self.pending_order_id:
                self.pending_order_id = None
                self.pending_kind = None
            logger.info(
                f"[FILL-ENTRY] {qty} 张 @ {px:.2f} fee={fee:.4f} | 累计 {self.pos_contracts} 张 "
                f"均价={self.entry_avg:.2f} 名义={self.open_notional:.2f} | TP={self._tp_price():.2f} SL={self._sl_price():.2f}"
            )
            return

        # 2) 平仓成交（逐笔累加，交易所净持仓归零才算平完）
        if oid == self.last_exit_oid or (oid == self.pending_order_id and self.pending_kind == "exit"):
            self.last_exit_oid = oid
            self.exit_fee += fee
            self.exit_contracts += qty
            self.exit_proceeds += qty * self.ct_val * px
            logger.info(
                f"[FILL-EXIT] {qty} 张 @ {px:.2f} fee={fee:.4f} | 累计平 {self.exit_contracts}/{self.pos_contracts} 张"
            )
            if abs(self._net_position()) < 1e-9 or self.exit_contracts >= self.pos_contracts - 1e-9:
                self._finalize_exit(px)
            return

        logger.info(f"[FILL-其他] {oid} {qty} 张 @ {px:.2f}（非本策略在途委托，忽略）")

    def _finalize_exit(self, last_px: float) -> None:
        exit_units = self.exit_contracts * self.ct_val
        exit_avg = self.exit_proceeds / exit_units if exit_units > 0 else last_px
        gross = (exit_avg - self.entry_avg) * self.pos_units * self.pos_side
        fees = self.entry_fee + self.exit_fee
        net_pnl = gross - fees
        self.cash += net_pnl
        self.realized_pnl += net_pnl
        self.trades += 1
        if net_pnl > 0:
            self.wins += 1
        reason = self.exit_reason
        if reason == "SL":
            self.sl_streak += 1
        elif reason == "TP":
            self.sl_streak = 0
        logger.info(
            f"[CLOSE-{reason or '?'}] 均价出={exit_avg:.2f} 入={self.entry_avg:.2f} | "
            f"毛利={gross:+.2f} 费={fees:.2f} 净={net_pnl:+.2f} USDT | 现金={self.cash:.2f} | "
            f"累计 {self.trades} 笔 胜率={100*self.wins/max(1,self.trades):.1f}%"
        )
        if reason == "SL" and self.sl_streak >= MAX_SL_STREAK:
            self.halt_until = datetime.fromtimestamp((_now_ms() + HALT_HOURS * 3_600_000) / 1000.0, timezone.utc)
            logger.error(
                f"!!! L3 熔断：连续 {self.sl_streak} 笔硬止损 → 停止开仓至 {self.halt_until.isoformat()} !!!"
            )
        self.in_position = False
        self.pos_side = 0
        self.pos_contracts = 0.0
        self.pos_units = 0.0
        self.open_notional = 0.0
        self.entry_avg = 0.0
        self.entry_fee = 0.0
        self.exit_fee = 0.0
        self.exit_proceeds = 0.0
        self.exit_contracts = 0.0
        self.exit_reason = ""
        self.order_step = 0
        self.pending_order_id = None
        self.pending_kind = None

    def _clear_pending(self, why: str) -> None:
        if self.pending_kind == "add":
            self.order_step = 1
        elif self.pending_kind == "entry":
            self.order_step = 0
        logger.error(
            f"[{why}] 在途委托 {self.pending_order_id} ({self.pending_kind}) 失效 → 状态回滚 "
            f"(order_step={self.order_step})"
        )
        self.pending_order_id = None
        self.pending_kind = None

    def on_order_denied(self, event: OrderDenied) -> None:
        logger.error(f"[DENIED] {event.client_order_id}: {event.reason}")
        self._clear_pending("DENIED")

    def on_order_rejected(self, event: OrderRejected) -> None:
        logger.error(f"[REJECTED] {event.client_order_id}: {event.reason}")
        self._clear_pending("REJECTED")

    def on_order_canceled(self, event: OrderCanceled) -> None:
        if event.client_order_id == self.pending_order_id:
            self._clear_pending("CANCELED")

    def on_order_expired(self, event: OrderExpired) -> None:
        if event.client_order_id == self.pending_order_id:
            self._clear_pending("EXPIRED")

    # ── 心跳 / 看门狗 ─────────────────────────────────────────────────────────
    def _on_heartbeat(self, event: object) -> None:
        now_ms = _now_ms()
        warm = (now_ms - self.started_ms) > 120_000

        if self.cash <= 0:
            equity = self._read_equity()
            if equity > 0:
                self.cash = equity
                self.start_cash = equity
                logger.warning(f"[WATCHDOG] 权益读取恢复: {equity:.2f} USDT → 允许交易")

        net = self._net_position()
        if warm:
            if abs(net) > 1e-9 and not self.in_position and self.pending_order_id is None:
                # 交易所持仓但策略无状态 → 接管，避免裸奔
                self.in_position = True
                self.pos_side = 1 if net > 0 else -1
                self.pos_contracts = abs(net)
                self.pos_units = self.pos_contracts * self.ct_val
                self.entry_avg = self.last_px if self.last_px > 0 else 0.0
                self.open_notional = self.pos_units * self.entry_avg
                self.order_step = 2
                logger.error(
                    f"[WATCHDOG] 发现无人管理的交易所持仓 net={net} → 按最新价 {self.entry_avg:.2f} 接管。"
                    f" TP/SL 以该价为基准，请人工确认!"
                )
            elif abs(net) < 1e-9 and self.in_position and self.pending_kind != "exit":
                logger.error("[WATCHDOG] 策略以为持仓，交易所已净空 → 强制复位状态")
                self.in_position = False
                self.pos_side = 0
                self.pos_contracts = 0.0
                self.pos_units = 0.0
                self.open_notional = 0.0
                self.entry_avg = 0.0
                self.order_step = 0

        # 行情中断且持仓 → 软件止损失效，立刻市价平掉
        if self.in_position and self.pending_order_id is None and self.last_bar_ms:
            stale_sec = (now_ms - self.last_bar_ms) / 1000.0
            if stale_sec > FEED_STALE_FLATTEN_SEC:
                logger.error(f"!!! 行情已 {stale_sec/60:.0f} 分钟未更新，软件止损不可依赖 → 市价强平 !!!")
                self._submit_exit("FEED_STALE", 0.0, "watchdog")

        logger.info(
            f"[HEARTBEAT] px={self.last_px:.2f} signal={self.sig.value} q={self.sig.q_val:+.3f} | "
            f"InPos={self.in_position} side={self.pos_side:+d} 张={self.pos_contracts} net={net} | "
            f"K线 15m/1m={self.bars_15m}/{self.bars_1m} | "
            f"cash={self.cash:.2f} 已平={self.trades} 胜率={100*self.wins/max(1,self.trades):.0f}% "
            f"PnL={self.realized_pnl:+.2f}"
            + (f" | 熔断至 {self.halt_until.isoformat()}" if self.halt_until else "")
        )


# ─── 入口 ─────────────────────────────────────────────────────────────────────
def main() -> None:
    logger.info("=" * 78)
    logger.info("NAUTILUS TRADER - 007 ETH AI TIMING (AlphaEvolve + Q-State 15m)")
    logger.info(f"Symbol: {SYMBOL} | Timeframe: 15m(信号) + 1m(止盈止损巡检)")
    logger.info(f"Mode: OKX {OKX_ENV} | Account: {OKX_ACCOUNT_ID} | Leverage: {LEVERAGE}x {MGN_MODE}")
    logger.info(
        f"Params: gamma={GAMMA} alpha={ALPHA} thresh={THRESH} tp={TP_PCT*100:.2f}% sl={SL_PCT*100:.2f}% "
        f"first={FIRST_RATIO*100:.0f}% add={ADD_RATIO*100:.0f}%"
    )
    logger.info("=" * 78)

    if not IS_LIVE:
        logger.warning("*** DEMO 模式（x-simulated-trading: 1）—— 不会动用真实资金 ***")

    set_okx_leverage(SYMBOL, LEVERAGE, MGN_MODE)

    node = (
        LiveNode.builder("AE007-NODE", TraderId.from_str("AE-007"), Environment.LIVE)
        .with_logging(LoggerConfig(stdout_level=LogLevel.WARNING))
        .with_reconciliation(reconciliation=True)
        .with_risk_engine_config(LiveRiskEngineConfig(bypass=True))
        .add_data_client(
            None,
            OKXDataClientFactory(),
            OKXDataClientConfig(
                instrument_types=[OKXInstrumentType.SWAP],
                environment=OKXEnvironment.LIVE if IS_LIVE else OKXEnvironment.DEMO,
                api_key=os.getenv("OKX_API_KEY", ""),
                api_secret=os.getenv("OKX_API_SECRET", ""),
                api_passphrase=os.getenv("OKX_API_PASSPHRASE", ""),
            ),
        )
        .add_exec_client(
            None,
            OKXExecutionClientFactory(),
            OKXExecutionClientConfig(
                account_id=AccountId.from_str(OKX_ACCOUNT_ID),
                instrument_types=[OKXInstrumentType.SWAP],
                environment=OKXEnvironment.LIVE if IS_LIVE else OKXEnvironment.DEMO,
                api_key=os.getenv("OKX_API_KEY", ""),
                api_secret=os.getenv("OKX_API_SECRET", ""),
                api_passphrase=os.getenv("OKX_API_PASSPHRASE", ""),
                margin_mode=OKXMarginMode.CROSS if MGN_MODE == "cross" else OKXMarginMode.ISOLATED,
            ),
        )
        .build()
    )

    cfg = AlphaEvolveConfig(
        strategy_id=StrategyId.from_str("AE-ETH"),
        order_id_tag="007",
        use_hyphens_in_client_order_ids=False,  # OKX clOrdId 只接受字母数字
    )
    cfg.instrument_id = f"{SYMBOL}.{OKX}"
    node.add_strategy(AlphaEvolveEthStrategy(cfg))
    logger.info(f"已注册策略 {SYMBOL}.{OKX} → 启动事件循环")
    node.run()


if __name__ == "__main__":
    main()
