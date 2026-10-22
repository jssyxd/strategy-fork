#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VectorBT Portfolio Backtest Engine for 007 ETH AI Timing Strategy.
Utilizes VectorBT's Portfolio simulation and performance analytics.
"""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from vectorbt.portfolio.base import Portfolio
from strategy_signals import (
    ADD_RATIO,
    FIRST_RATIO,
    LOOKBACK,
    SL_PCT,
    TAKER_FEE,
    THRESH,
    TP_PCT,
    AlphaEvolveSignal,
)

DATA_PATH = Path("/mnt/iflow/database/03_governed_lake/v2_parquet_lake/crypto/futures_swap/ETH-USDT-SWAP/15m/ETH-USDT-SWAP_15m_governed.parquet")
START_TS_MS = int(pd.Timestamp("2026-10-04 00:00:00+00:00").timestamp() * 1000)
END_TS_MS = int(pd.Timestamp("2026-10-21 00:00:00+00:00").timestamp() * 1000)


@dataclass
class VbtTradeRecord:
    trade_id: int
    side: str
    entry_time_utc: str
    exit_time_utc: str
    hold_hours: float
    entry_avg_price: float
    exit_price: float
    position_size_eth: float
    notional_usdt: float
    order_steps: int
    gross_pnl_usdt: float
    fee_usdt: float
    net_pnl_usdt: float
    return_pct: float
    exit_reason: str
    entry_rule_ref: str
    entry_rule_desc: str
    exit_rule_ref: str
    exit_rule_desc: str


class VectorBTBacktestEngine:
    def __init__(
        self,
        initial_capital: float = 750.0,
        taker_fee: float = TAKER_FEE,
        slippage: float = 0.0,
    ) -> None:
        self.initial_capital = initial_capital
        self.taker_fee = taker_fee
        self.slippage = slippage

    def run(self) -> Dict[str, Any]:
        df = pd.read_parquet(DATA_PATH).sort_values("ts_init").reset_index(drop=True)

        all_bars = []
        for _, r in df.iterrows():
            all_bars.append({
                "ts": int(r["ts_init"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
                "datetime_open": str(r["datetime_open"]),
            })

        sig_engine = AlphaEvolveSignal()
        all_signals = [sig_engine.update(b["open"], b["high"], b["low"], b["close"]) for b in all_bars]

        start_idx = [i for i, b in enumerate(all_bars) if b["ts"] >= START_TS_MS][0]
        end_idx = [i for i, b in enumerate(all_bars) if b["ts"] < END_TS_MS][-1] + 1

        sub_bars = all_bars[start_idx:end_idx]
        sub_signals = all_signals[start_idx:end_idx]

        # VectorBT simulation with order arrays
        n_bars = len(sub_bars)
        timestamps = [pd.Timestamp(b["datetime_open"]) for b in sub_bars]
        close_series = pd.Series([b["close"] for b in sub_bars], index=timestamps)

        orders_size = np.zeros(n_bars, dtype=float)
        orders_price = np.zeros(n_bars, dtype=float)

        cash = self.initial_capital
        pos_side = 0
        units = 0.0
        avg_px = 0.0
        open_notional = 0.0
        order_step = 0
        entry_ts = None
        entry_idx = 0
        entry_fees = 0.0
        entry_notional_sum = 0.0

        equity_curve: List[Dict[str, Any]] = []
        closed_trades: List[VbtTradeRecord] = []
        fees_total = 0.0

        def calc_mtm(px: float) -> float:
            if pos_side == 0 or units == 0.0:
                return cash
            return cash + (px - avg_px) * units * pos_side

        for i, b in enumerate(sub_bars):
            sig = sub_signals[i]
            price = b["close"]

            # 1. Exit check
            if pos_side != 0 and units > 0.0:
                tp_target = avg_px * (1.0 + TP_PCT) if pos_side == 1 else avg_px * (1.0 - TP_PCT)
                sl_target = avg_px * (1.0 - SL_PCT) if pos_side == 1 else avg_px * (1.0 + SL_PCT)
                hit = None

                if pos_side == 1:
                    if b["high"] >= tp_target:
                        hit = ("TP", tp_target)
                    elif b["low"] <= sl_target:
                        hit = ("SL", sl_target)
                else:
                    if b["low"] <= tp_target:
                        hit = ("TP", tp_target)
                    elif b["high"] >= sl_target:
                        hit = ("SL", sl_target)

                if hit is not None:
                    reason, fill_target = hit
                    fill_px = fill_target * (1.0 - self.slippage) if pos_side == 1 else fill_target * (1.0 + self.slippage)
                    exit_notional = units * fill_px
                    exit_fee = exit_notional * self.taker_fee
                    gross_pnl = (fill_px - avg_px) * units * pos_side
                    net_pnl = gross_pnl - entry_fees - exit_fee

                    cash += gross_pnl - exit_fee
                    fees_total += exit_fee

                    # VectorBT order: close position
                    orders_size[i] = -units if pos_side == 1 else units
                    orders_price[i] = fill_px

                    side_str = "LONG" if pos_side == 1 else "SHORT"
                    entry_rule_ref = "策略第5条·多头开仓与加仓" if pos_side == 1 else "策略第5条·空头开仓与加仓"
                    entry_rule_desc = (
                        f"遵循策略第5条: composite_sig > +1.20 极值开多，首仓50%保证金"
                        if pos_side == 1
                        else f"遵循策略第5条: composite_sig < -1.20 极值开空，首仓50%保证金"
                    )
                    if order_step == 2:
                        entry_rule_desc += "；后续同向信号确认追加75%剩余保证金"

                    if reason == "TP":
                        exit_rule_ref = "策略第4条·动态追踪快速止盈"
                        exit_rule_desc = f"遵循策略第4条: 触及均价 +0.90% 目标价 {fill_px:.2f}，全额市价止盈"
                    else:
                        exit_rule_ref = "策略第4条·硬性安全截断止损"
                        exit_rule_desc = f"遵循策略第4条: 触及均价 -2.50% 止损价 {fill_px:.2f}，全额市价止损"

                    trade_rec = VbtTradeRecord(
                        trade_id=len(closed_trades) + 1,
                        side=side_str,
                        entry_time_utc=sub_bars[entry_idx]["datetime_open"],
                        exit_time_utc=b["datetime_open"],
                        hold_hours=round((b["ts"] - entry_ts) / 3600000.0, 2),
                        entry_avg_price=round(avg_px, 2),
                        exit_price=round(fill_px, 2),
                        position_size_eth=round(units, 4),
                        notional_usdt=round(entry_notional_sum, 2),
                        order_steps=order_step,
                        gross_pnl_usdt=round(gross_pnl, 2),
                        fee_usdt=round(entry_fees + exit_fee, 2),
                        net_pnl_usdt=round(net_pnl, 2),
                        return_pct=round(net_pnl / entry_notional_sum * 100.0, 2),
                        exit_reason=reason,
                        entry_rule_ref=entry_rule_ref,
                        entry_rule_desc=entry_rule_desc,
                        exit_rule_ref=exit_rule_ref,
                        exit_rule_desc=exit_rule_desc,
                    )
                    closed_trades.append(trade_rec)

                    pos_side = 0
                    units = 0.0
                    avg_px = 0.0
                    open_notional = 0.0
                    order_step = 0
                    entry_ts = None
                    entry_fees = 0.0
                    entry_notional_sum = 0.0

                    equity_curve.append({
                        "ts": b["ts"],
                        "datetime_utc": b["datetime_open"],
                        "equity": round(cash, 2),
                        "cash": round(cash, 2),
                        "pos_side": 0,
                        "units": 0.0,
                    })
                    continue

            # 2. Entry / Pyramiding
            if sig is not None:
                want_side = 1 if sig > THRESH else (-1 if sig < -THRESH else 0)

                if pos_side == 0 and want_side != 0:
                    available = cash
                    alloc = available * FIRST_RATIO
                    fill_px = price * (1.0 + self.slippage) if want_side == 1 else price * (1.0 - self.slippage)
                    u = alloc / fill_px
                    fee = alloc * self.taker_fee
                    cash -= fee
                    fees_total += fee

                    units = u
                    avg_px = fill_px
                    pos_side = want_side
                    order_step = 1
                    open_notional = alloc
                    entry_notional_sum = alloc
                    entry_fees = fee
                    entry_ts = b["ts"]
                    entry_idx = i

                    orders_size[i] = u if want_side == 1 else -u
                    orders_price[i] = fill_px

                elif pos_side != 0 and order_step == 1 and want_side == pos_side:
                    available = max(0.0, cash - open_notional)
                    alloc = available * ADD_RATIO
                    if alloc > 0.0:
                        fill_px = price * (1.0 + self.slippage) if pos_side == 1 else price * (1.0 - self.slippage)
                        u = alloc / fill_px
                        fee = alloc * self.taker_fee
                        cash -= fee
                        fees_total += fee

                        avg_px = (avg_px * units + fill_px * u) / (units + u)
                        units += u
                        open_notional += alloc
                        entry_notional_sum += alloc
                        entry_fees += fee
                        order_step = 2

                        orders_size[i] = u if pos_side == 1 else -u
                        orders_price[i] = fill_px

            current_eq = calc_mtm(price)
            equity_curve.append({
                "ts": b["ts"],
                "datetime_utc": b["datetime_open"],
                "equity": round(current_eq, 2),
                "cash": round(cash, 2),
                "pos_side": pos_side,
                "units": round(units, 4),
            })

        # Run VectorBT native Portfolio analytics
        vbt_portfolio = Portfolio.from_orders(
            close=close_series,
            size=pd.Series(orders_size, index=timestamps),
            price=pd.Series(np.where(orders_price > 0, orders_price, close_series), index=timestamps),
            fees=self.taker_fee,
            init_cash=self.initial_capital,
        )

        final_equity = equity_curve[-1]["equity"]
        total_ret = (final_equity / self.initial_capital) - 1.0
        days = (sub_bars[-1]["ts"] - sub_bars[0]["ts"]) / 86400000.0
        cagr = (final_equity / self.initial_capital) ** (365.0 / days) - 1.0 if days > 0 else 0.0

        eq_values = [p["equity"] for p in equity_curve]
        peak = -1e9
        mdd = 0.0
        for eq in eq_values:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0.0
            if dd > mdd:
                mdd = dd

        df_eq = pd.DataFrame(equity_curve)
        df_eq["dt"] = pd.to_datetime(df_eq["datetime_utc"])
        df_eq["date"] = df_eq["dt"].dt.date
        daily_close = df_eq.groupby("date")["equity"].last().pct_change().dropna()
        if len(daily_close) > 1 and daily_close.std() > 0:
            sharpe = (daily_close.mean() / daily_close.std()) * math.sqrt(365)
            downside = [min(0.0, r) for r in daily_close]
            dvar = sum(x * x for x in downside) / len(downside) if len(downside) > 0 else 0.0
            dsd = math.sqrt(dvar)
            sortino = (daily_close.mean() / dsd * math.sqrt(365)) if dsd > 0 else 0.0
        else:
            sharpe = 0.0
            sortino = 0.0
        calmar = (cagr / mdd) if mdd > 0 else 0.0
        wins = [t for t in closed_trades if t.net_pnl_usdt > 0]
        losses = [t for t in closed_trades if t.net_pnl_usdt <= 0]
        gross_win = sum(t.gross_pnl_usdt for t in wins)
        gross_loss = abs(sum(t.gross_pnl_usdt for t in losses))
        pf = gross_win / gross_loss if gross_loss > 0 else 999.0
        win_rate = len(wins) / len(closed_trades) if closed_trades else 0.0

        metrics = {
            "engine": "VectorBT",
            "symbol": "ETH-USDT-SWAP",
            "start_time_utc": sub_bars[0]["datetime_open"],
            "end_time_utc": sub_bars[-1]["datetime_open"],
            "total_bars": len(sub_bars),
            "initial_capital": self.initial_capital,
            "final_equity": round(final_equity, 2),
            "final_cash": round(cash, 2),
            "total_return_pct": round(total_ret * 100.0, 2),
            "cagr_pct": round(cagr * 100.0, 2),
            "max_drawdown_pct": round(mdd * 100.0, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "calmar_ratio": round(calmar, 2),
            "profit_factor": round(pf, 3),
            "total_trades": len(closed_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": round(win_rate * 100.0, 2),
            "total_fees_usdt": round(fees_total, 2),
            "open_position_at_end": {
                "pos_side": pos_side,
                "units": round(units, 4),
                "avg_price": round(avg_px, 2),
                "unrealized_pnl": round((sub_bars[-1]["close"] - avg_px) * units * pos_side, 2) if pos_side != 0 else 0.0,
            }
        }

        os.makedirs("reports", exist_ok=True)
        with open("reports/vectorbt_metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

        with open("reports/vectorbt_trades.json", "w", encoding="utf-8") as f:
            json.dump([asdict(t) for t in closed_trades], f, indent=2, ensure_ascii=False)

        df_orig = pd.DataFrame([
            {
                "序号": t.trade_id,
                "方向": t.side,
                "开仓时间(UTC)": t.entry_time_utc[:16],
                "平仓时间(UTC)": t.exit_time_utc[:16],
                "持仓小时": t.hold_hours,
                "开仓均价": t.entry_avg_price,
                "平仓价": t.exit_price,
                "ETH数量": t.position_size_eth,
                "名义价值USDT": t.notional_usdt,
                "毛利USDT": t.gross_pnl_usdt,
                "手续费USDT": t.fee_usdt,
                "净利USDT": t.net_pnl_usdt,
                "出场原因": t.exit_reason,
                "遵循策略条款": f"{t.entry_rule_ref} | {t.exit_rule_ref}",
                "动作详细说明": f"{t.entry_rule_desc}；{t.exit_rule_desc}",
            }
            for t in closed_trades
        ])
        df_orig.to_csv("reports/vectorbt_trades.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame(equity_curve).to_csv("reports/vectorbt_equity.csv", index=False)

        print("VectorBT Backtest Completed Successfully:")
        print(f"  Total Closed Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate_pct']}%")
        print(f"  Total Return: {metrics['total_return_pct']}%")
        print(f"  Max Drawdown: {metrics['max_drawdown_pct']}%")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']}")
        print(f"  Final Equity: {metrics['final_equity']} USDT")

        return {
            "metrics": metrics,
            "trades": closed_trades,
            "equity_curve": equity_curve,
            "vbt_portfolio": vbt_portfolio,
        }


if __name__ == "__main__":
    engine = VectorBTBacktestEngine()
    engine.run()
