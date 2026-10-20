#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""007 ETH AlphaEvolve 15m —— 回测引擎（口径与服务器部署的 smc_eth_007_live.py 一致）

信号实现直接 import 生产模块的 AlphaEvolveSignal，保证回测与实盘同一份代码。
成本模型：Maker 0.02% / Taker 0.05%，手续费按**开仓名义价值**计（名义价值 = 张数 × ctVal × 价格，
与杠杆倍数无关；10x 杠杆只是把保证金压到名义值的 1/10）。

用法：
  python backtest_007_pine.py --csv /tmp/eth15m_1y.csv --days 365 \
      --entry-fee 0.0005 --exit-fee 0.0005 --slippage 0 \
      --out-dir . --prefix alpha_1y
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from smc_eth_007_live import AlphaEvolveSignal  # noqa: E402  生产代码同一份信号实现

# ── 与部署代码一致的策略参数 ────────────────────────────────────────────────
THRESH = 1.20
TP_PCT = 0.0090
SL_PCT = 0.0250
FIRST_RATIO = 0.50
ADD_RATIO = 0.75
LOOKBACK = 20


def load_bars(path: str) -> list[dict]:
    bars = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            bars.append(
                dict(
                    ts=int(r["ts"]),
                    o=float(r["open"]),
                    h=float(r["high"]),
                    l=float(r["low"]),
                    c=float(r["close"]),
                    v=float(r.get("vol") or 0.0),
                )
            )
    bars.sort(key=lambda b: b["ts"])
    return bars


def compute_signals(bars: list[dict]) -> list[float | None]:
    sig = AlphaEvolveSignal()
    return [sig.update(b["o"], b["h"], b["l"], b["c"]) for b in bars]


def simulate(
    bars: list[dict],
    signals: list[float | None],
    initial_capital: float = 10_000.0,
    entry_fee: float = 0.0005,
    exit_fee: float = 0.0005,
    slippage: float = 0.0,
) -> dict:
    """按部署代码的状态机逐根 15m K 线回放。

    入场：信号收盘价成交（市价单）→ 吃 entry_fee + 滑点
    出场：盘中触及 TP/SL 价成交 → 吃 exit_fee + 滑点
    加仓：同向信号在下一根 K 线仍成立、且尚未加仓（order_step==1）时执行
    """
    cash = initial_capital          # 只记已实现：初始资金 + 已实现盈亏 - 手续费
    pos_side = 0
    units = 0.0                     # ETH 数量
    avg = 0.0
    open_notional = 0.0
    order_step = 0
    entry_ts = None
    entry_idx = 0
    entry_fees = 0.0
    entry_notional_sum = 0.0

    equity_curve: list[tuple[int, float]] = []
    trades: list[dict] = []
    fees_total = 0.0

    def mtm(px: float) -> float:
        if pos_side == 0 or units == 0:
            return cash
        return cash + (px - avg) * units * pos_side

    for i, b in enumerate(bars):
        sig = signals[i]
        price = b["c"]

        # 1) 出场优先（TP 先于 SL，与部署代码及 Pine 一致）
        if pos_side != 0 and units > 0:
            tp_px = avg * (1 + TP_PCT) if pos_side == 1 else avg * (1 - TP_PCT)
            sl_px = avg * (1 - SL_PCT) if pos_side == 1 else avg * (1 + SL_PCT)
            hit = None
            if pos_side == 1:
                if b["h"] >= tp_px:
                    hit = ("TP", tp_px)
                elif b["l"] <= sl_px:
                    hit = ("SL", sl_px)
            else:
                if b["l"] <= tp_px:
                    hit = ("TP", tp_px)
                elif b["h"] >= sl_px:
                    hit = ("SL", sl_px)
            if hit is not None:
                reason, trigger = hit
                fill = trigger * (1 - slippage) if pos_side == 1 else trigger * (1 + slippage)
                exit_notional = units * fill
                fee = exit_notional * exit_fee
                gross = (fill - avg) * units * pos_side
                cash += gross - fee
                fees_total += fee
                trades.append(
                    dict(
                        side="LONG" if pos_side == 1 else "SHORT",
                        entry_ts=entry_ts,
                        exit_ts=b["ts"],
                        hold_bars=i - entry_idx,
                        entry_avg=avg,
                        exit_avg=fill,
                        units=units,
                        notional=entry_notional_sum,
                        gross_pnl=gross,
                        entry_fee=entry_fees,
                        exit_fee=fee,
                        fees=entry_fees + fee,
                        net_pnl=gross - entry_fees - fee,
                        reason=reason,
                    )
                )
                pos_side = 0
                units = 0.0
                avg = 0.0
                open_notional = 0.0
                order_step = 0
                entry_ts = None
                entry_fees = 0.0
                entry_notional_sum = 0.0
                equity_curve.append((b["ts"], cash))
                continue

        # 2) 入场 / 加仓
        if sig is not None:
            want_side = 1 if sig > THRESH else (-1 if sig < -THRESH else 0)
            if pos_side == 0 and want_side != 0:
                available = cash
                alloc = available * FIRST_RATIO
                fill = price * (1 + slippage) if want_side == 1 else price * (1 - slippage)
                u = alloc / fill
                fee = alloc * entry_fee
                cash -= fee
                fees_total += fee
                units = u
                avg = fill
                pos_side = want_side
                order_step = 1
                open_notional = alloc
                entry_notional_sum = alloc
                entry_fees = fee
                entry_ts = b["ts"]
                entry_idx = i
            elif pos_side != 0 and order_step == 1 and want_side == pos_side:
                available = max(0.0, cash - open_notional)
                alloc = available * ADD_RATIO
                if alloc > 0:
                    fill = price * (1 + slippage) if pos_side == 1 else price * (1 - slippage)
                    u = alloc / fill
                    fee = alloc * entry_fee
                    cash -= fee
                    fees_total += fee
                    units += u
                    avg = (avg * (units - u) + fill * u) / units
                    open_notional += alloc
                    entry_notional_sum += alloc
                    entry_fees += fee
                    order_step = 2

        equity_curve.append((b["ts"], mtm(price)))

    # 期末仍有持仓：按最后一根收盘价盯市，不强行平仓（与实盘一致：策略不会在收盘强平）
    open_at_end = None
    if pos_side != 0:
        last = bars[-1]
        open_at_end = dict(
            side="LONG" if pos_side == 1 else "SHORT",
            entry_ts=entry_ts,
            entry_avg=avg,
            units=units,
            notional=entry_notional_sum,
            unrealized=(last["c"] - avg) * units * pos_side,
            mark_px=last["c"],
        )

    return dict(
        initial_capital=initial_capital,
        final_equity=equity_curve[-1][1] if equity_curve else initial_capital,
        cash=cash,
        equity_curve=equity_curve,
        trades=trades,
        fees_total=fees_total,
        open_at_end=open_at_end,
        entry_fee=entry_fee,
        exit_fee=exit_fee,
        slippage=slippage,
    )


def max_drawdown(curve: list[tuple[int, float]]) -> tuple[float, int, int]:
    peak = -1e18
    peak_i = 0
    mdd = 0.0
    dd_start = dd_end = 0
    for i, (_, eq) in enumerate(curve):
        if eq > peak:
            peak = eq
            peak_i = i
        dd = (peak - eq) / peak if peak > 0 else 0.0
        if dd > mdd:
            mdd = dd
            dd_start = peak_i
            dd_end = i
    return mdd, dd_start, dd_end


def daily_equity(curve: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """每个 UTC 自然日取当日最后一根的权益。"""
    out = []
    cur_day = None
    cur_eq = None
    for ts, eq in curve:
        day = ts // 86_400_000
        if day != cur_day:
            if cur_day is not None:
                out.append((cur_day * 86_400_000, cur_eq))
            cur_day = day
        cur_eq = eq
    if cur_day is not None:
        out.append((cur_day * 86_400_000, cur_eq))
    return out


def compute_metrics(res: dict, bars: list[dict]) -> dict:
    curve = res["equity_curve"]
    trades = res["trades"]
    initial = res["initial_capital"]
    final = res["final_equity"]
    start_ts, end_ts = curve[0][0], curve[-1][0]
    days = (end_ts - start_ts) / 86_400_000
    total_ret = final / initial - 1
    cagr = (final / initial) ** (365.0 / days) - 1 if days > 0 and final > 0 else float("nan")
    mdd, dd_s, dd_e = max_drawdown(curve)

    d_eq = daily_equity(curve)
    rets = []
    for i in range(1, len(d_eq)):
        prev = d_eq[i - 1][1]
        if prev > 0:
            rets.append(d_eq[i][1] / prev - 1)
    if len(rets) >= 2:
        mean_r = sum(rets) / len(rets)
        var = sum((r - mean_r) ** 2 for r in rets) / (len(rets) - 1)
        sd = math.sqrt(var)
        sharpe = mean_r / sd * math.sqrt(365) if sd > 0 else float("nan")
        downside = [min(0.0, r) for r in rets]
        dvar = sum(x * x for x in downside) / len(downside)
        dsd = math.sqrt(dvar)
        sortino = mean_r / dsd * math.sqrt(365) if dsd > 0 else float("nan")
    else:
        mean_r = sd = sharpe = sortino = float("nan")
    calmar = cagr / mdd if mdd > 0 else float("inf")

    pnls = [t["net_pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    win_rate = len(wins) / len(pnls) if pnls else 0.0
    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0

    # 连亏 / 连盈
    max_consec_loss = max_consec_win = cur_l = cur_w = 0
    for p in pnls:
        if p <= 0:
            cur_l += 1
            cur_w = 0
        else:
            cur_w += 1
            cur_l = 0
        max_consec_loss = max(max_consec_loss, cur_l)
        max_consec_win = max(max_consec_win, cur_w)

    longs = [t for t in trades if t["side"] == "LONG"]
    shorts = [t for t in trades if t["side"] == "SHORT"]
    hold = [t["hold_bars"] for t in trades]

    # 名义价值/手续费口径
    peak_notional = max([t["notional"] for t in trades], default=0.0)
    turnover_notional = sum(t["notional"] for t in trades) * 2.0  # 开+平
    fee_share = res["fees_total"] / (gross_win - gross_loss) if (gross_win - gross_loss) != 0 else float("nan")

    return dict(
        start_date=datetime.fromtimestamp(start_ts / 1000, timezone.utc).strftime("%Y-%m-%d"),
        end_date=datetime.fromtimestamp(end_ts / 1000, timezone.utc).strftime("%Y-%m-%d"),
        trade_first=datetime.fromtimestamp(trades[0]["entry_ts"] / 1000, timezone.utc).strftime("%Y-%m-%d")
        if trades
        else None,
        trade_last=datetime.fromtimestamp(trades[-1]["exit_ts"] / 1000, timezone.utc).strftime("%Y-%m-%d")
        if trades
        else None,
        days=days,
        bars=len(bars),
        initial_capital=initial,
        final_equity=final,
        total_return=total_ret,
        cagr=cagr,
        mdd=mdd,
        mdd_start=datetime.fromtimestamp(curve[dd_s][0] / 1000, timezone.utc).strftime("%Y-%m-%d"),
        mdd_end=datetime.fromtimestamp(curve[dd_e][0] / 1000, timezone.utc).strftime("%Y-%m-%d"),
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        trades=len(trades),
        win_rate=win_rate,
        profit_factor=pf,
        avg_win=avg_win,
        avg_loss=avg_loss,
        win_loss_ratio=avg_win / avg_loss if avg_loss > 0 else float("inf"),
        max_consec_loss=max_consec_loss,
        max_consec_win=max_consec_win,
        fees_total=res["fees_total"],
        fee_share=fee_share,
        peak_notional=peak_notional,
        turnover_notional=turnover_notional,
        avg_notional=sum(t["notional"] for t in trades) / len(trades) if trades else 0.0,
        avg_hold_hours=sum(hold) / len(hold) * 0.25 if hold else 0.0,
        long_trades=len(longs),
        short_trades=len(shorts),
        long_pnl=sum(t["net_pnl"] for t in longs),
        short_pnl=sum(t["net_pnl"] for t in shorts),
        long_win=sum(1 for t in longs if t["net_pnl"] > 0) / len(longs) if longs else 0.0,
        short_win=sum(1 for t in shorts if t["net_pnl"] > 0) / len(shorts) if shorts else 0.0,
        tp_count=sum(1 for t in trades if t["reason"] == "TP"),
        sl_count=sum(1 for t in trades if t["reason"] == "SL"),
        realized_pnl=sum(t["net_pnl"] for t in trades),
        unrealized=(res["open_at_end"] or {}).get("unrealized", 0.0),
        open_at_end=res["open_at_end"],
        daily=len(rets),
        daily_vol=(sd * math.sqrt(365)) if len(rets) >= 2 else float("nan"),
        best_trade=max(pnls) if pnls else 0.0,
        worst_trade=min(pnls) if pnls else 0.0,
    )


def monthly_returns(curve: list[tuple[int, float]]) -> list[tuple[str, float]]:
    months: dict[str, tuple[float, float]] = {}
    for ts, eq in curve:
        key = datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m")
        first, _ = months.get(key, (eq, eq))
        months[key] = (first, eq)
    return [(k, v[1] / v[0] - 1) for k, v in sorted(months.items())]


def run_window(bars: list[dict], signals: list[float | None], start_idx: int, end_idx: int, **kw) -> dict:
    sub_bars = bars[start_idx:end_idx]
    sub_sig = signals[start_idx:end_idx]
    # 用前面全部历史做指标预热（信号本身已带记忆，不需要重新暖机）
    res = simulate(sub_bars, sub_sig, **kw)
    return dict(res=res, metrics=compute_metrics(res, sub_bars))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="/tmp/eth15m_1y.csv")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--initial", type=float, default=10_000.0)
    ap.add_argument("--entry-fee", type=float, default=0.0005)
    ap.add_argument("--exit-fee", type=float, default=0.0005)
    ap.add_argument("--slippage", type=float, default=0.0)
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--prefix", default="alpha_1y")
    args = ap.parse_args()

    bars = load_bars(args.csv)
    signals = compute_signals(bars)
    end_idx = len(bars)
    start_idx = max(0, end_idx - args.days * 96)

    main_run = run_window(
        bars, signals, start_idx, end_idx,
        initial_capital=args.initial,
        entry_fee=args.entry_fee,
        exit_fee=args.exit_fee,
        slippage=args.slippage,
    )
    m = main_run["metrics"]
    res = main_run["res"]

    # 敏感性：maker 双侧 / 加滑点
    variants = {}
    for name, ef, xf, sl in [
        ("zero_fee", 0.0, 0.0, 0.0),
        ("taker_5bp", 0.0005, 0.0005, 0.0),
        ("maker_2bp", 0.0002, 0.0002, 0.0),
        ("taker_5bp_slip2bp", 0.0005, 0.0005, 0.0002),
        ("taker_5bp_slip5bp", 0.0005, 0.0005, 0.0005),
    ]:
        v = run_window(bars, signals, start_idx, end_idx,
                       initial_capital=args.initial, entry_fee=ef, exit_fee=xf, slippage=sl)
        variants[name] = v["metrics"]

    # 子窗口（近 30 / 131 / 365 天）
    subs = {}
    for label, d in [("30d", 30), ("131d", 131), ("365d", 365), ("full", int(10_000))]:
        s_idx = max(0, end_idx - d * 96)
        if s_idx >= end_idx - 96:
            continue
        v = run_window(bars, signals, s_idx, end_idx,
                       initial_capital=args.initial, entry_fee=args.entry_fee,
                       exit_fee=args.exit_fee, slippage=args.slippage)
        subs[label] = v["metrics"]

    out = dict(meta=dict(csv=args.csv, fee_model=dict(maker=0.0002, taker=0.0005,
                                                      entry_fee=args.entry_fee, exit_fee=args.exit_fee,
                                                      slippage=args.slippage),
                         params=dict(thresh=THRESH, tp=TP_PCT, sl=SL_PCT,
                                     first=FIRST_RATIO, add=ADD_RATIO, lookback=LOOKBACK)),
               metrics=m, variants=variants, windows=subs,
               monthly=monthly_returns(res["equity_curve"]),
               equity_series=[[ts, round(eq, 2)] for ts, eq in res["equity_curve"][::32]],
               daily_series=[[ts, round(eq, 2)] for ts, eq in daily_equity(res["equity_curve"])],
               trades=[{**t,
                        "entry_dt": datetime.fromtimestamp(t["entry_ts"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M"),
                        "exit_dt": datetime.fromtimestamp(t["exit_ts"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")}
                       for t in res["trades"]],
               equity=res["equity_curve"])

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, f"{args.prefix}_metrics.json"), "w") as fh:
        json.dump({k: v for k, v in out.items() if k != "equity"}, fh, ensure_ascii=False, indent=2, default=str)

    # 逐笔 CSV
    with open(os.path.join(args.out_dir, f"{args.prefix}_trades.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["序号", "方向", "开仓时间(UTC)", "平仓时间(UTC)", "持仓小时", "开仓均价", "平仓价",
                    "ETH数量", "名义价值USDT", "毛利USDT", "手续费USDT", "净利USDT", "出场原因"])
        for i, t in enumerate(out["trades"], 1):
            w.writerow([i, t["side"], t["entry_dt"], t["exit_dt"], round(t["hold_bars"] * 0.25, 2),
                        round(t["entry_avg"], 2), round(t["exit_avg"], 2), round(t["units"], 4),
                        round(t["notional"], 2), round(t["gross_pnl"], 2), round(t["fees"], 2),
                        round(t["net_pnl"], 2), t["reason"]])

    print(json.dumps({k: v for k, v in m.items() if k != "open_at_end"}, ensure_ascii=False, indent=2, default=str))
    print("\n=== 敏感性 ===")
    for k, v in variants.items():
        print(f"{k:22s} ret={v['total_return']*100:7.2f}% mdd={v['mdd']*100:6.2f}% pf={v['profit_factor']:.3f} wr={v['win_rate']*100:.1f}%")
    print("\n=== 子窗口 ===")
    for k, v in subs.items():
        print(f"{k:6s} {v['start_date']}~{v['end_date']} ret={v['total_return']*100:7.2f}% cagr={v['cagr']*100:7.2f}% sharpe={v['sharpe']:.2f} sortino={v['sortino']:.2f} calmar={v['calmar']:.2f} trades={v['trades']} wr={v['win_rate']*100:.1f}% pf={v['profit_factor']:.2f}")


if __name__ == "__main__":
    main()
