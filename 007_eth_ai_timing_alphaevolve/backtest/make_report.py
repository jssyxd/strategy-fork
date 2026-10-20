#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 backtest_007_pine.py 产出的 metrics.json 渲染成自包含 HTML 回测报告。"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone


def pct(x: float, d: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x * 100:,.{d}f}%"


def num(x: float, d: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:,.{d}f}"


def ts_date(ts: int) -> str:
    return datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m-%d")


def nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    """生成「好看」的刻度，支持小于 1 的跨度（百分比/回撤曲线）。"""
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / max(1, n - 1)
    if raw <= 0:
        return [lo]
    mag = 10 ** math.floor(math.log10(raw))
    step = 10 * mag
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw:
            step = m * mag
            break
    start = math.floor(lo / step) * step
    ticks, v = [], start
    guard = 0
    while v <= hi + step * 0.001 and guard < 200:
        if v >= lo - step * 0.001:
            ticks.append(round(v, 10))
        v += step
        guard += 1
    return ticks


def line_chart(points, w, h, pad_l=70, pad_r=24, pad_t=20, pad_b=34, baseline=None,
               color="#58a6ff", fill="rgba(88,166,255,0.10)", y_fmt=lambda v: f"{v:,.0f}",
               x_fmt=ts_date, xticks=6) -> str:
    if not points:
        return ""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    lo, hi = min(ys), max(ys)
    if baseline is not None:
        lo = min(lo, baseline)
        hi = max(hi, baseline)
    if hi == lo:
        hi = lo + 1
    pad = (hi - lo) * 0.08
    lo -= pad
    hi += pad
    iw = w - pad_l - pad_r
    ih = h - pad_t - pad_b

    def X(ts):
        return pad_l + (ts - xs[0]) / (xs[-1] - xs[0]) * iw

    def Y(v):
        return pad_t + (hi - v) / (hi - lo) * ih

    path = " ".join(f"{'M' if i == 0 else 'L'}{X(x):.1f},{Y(y):.1f}" for i, (x, y) in enumerate(points))
    area = path + f" L{X(xs[-1]):.1f},{Y(lo):.1f} L{X(xs[0]):.1f},{Y(lo):.1f} Z"

    out = [f'<svg viewBox="0 0 {w} {h}" class="chart" xmlns="http://www.w3.org/2000/svg">']
    # 网格与 Y 轴
    for t in nice_ticks(lo, hi, 5):
        y = Y(t)
        if pad_t - 1 <= y <= h - pad_b + 1:
            out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-pad_r}" y2="{y:.1f}" stroke="#21262d"/>')
            out.append(f'<text x="{pad_l-8}" y="{y+4:.1f}" class="ax" text-anchor="end">{y_fmt(t)}</text>')
    # X 轴刻度
    for i in range(xticks):
        ts = xs[0] + (xs[-1] - xs[0]) * i / (xticks - 1)
        x = X(ts)
        anchor = "start" if i == 0 else ("end" if i == xticks - 1 else "middle")
        out.append(f'<text x="{x:.1f}" y="{h-10}" class="ax" text-anchor="{anchor}">{x_fmt(int(ts))}</text>')
    if baseline is not None:
        yb = Y(baseline)
        out.append(f'<line x1="{pad_l}" y1="{yb:.1f}" x2="{w-pad_r}" y2="{yb:.1f}" stroke="#8b949e" '
                   f'stroke-dasharray="4 4" stroke-width="1"/>')
        out.append(f'<text x="{w-pad_r-4}" y="{yb-6:.1f}" class="ax" text-anchor="end" fill="#8b949e">初始 {y_fmt(baseline)}</text>')
    out.append(f'<path d="{area}" fill="{fill}" stroke="none"/>')
    out.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.8"/>')
    out.append("</svg>")
    return "".join(out)


def bar_chart(items, w, h, pad_l=60, pad_r=16, pad_t=16, pad_b=46, label_every=1, value_labels=None) -> str:
    """items: [(label, value)]，正绿负红。"""
    if not items:
        return ""
    vals = [v for _, v in items]
    lo = min(0.0, min(vals))
    hi = max(0.0, max(vals))
    if hi == lo:
        hi = lo + 1
    pad = (hi - lo) * 0.12
    hi += pad
    if lo < 0:
        lo -= pad
    iw = w - pad_l - pad_r
    ih = h - pad_t - pad_b

    def Y(v):
        return pad_t + (hi - v) / (hi - lo) * ih

    bw = iw / len(items) * 0.62
    out = [f'<svg viewBox="0 0 {w} {h}" class="chart" xmlns="http://www.w3.org/2000/svg">']
    for t in nice_ticks(lo, hi, 4):
        y = Y(t)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-pad_r}" y2="{y:.1f}" stroke="#21262d"/>')
        out.append(f'<text x="{pad_l-8}" y="{y+4:.1f}" class="ax" text-anchor="end">{t*100:.0f}%</text>')
    y0 = Y(0)
    for i, (label, v) in enumerate(items):
        cx = pad_l + iw * (i + 0.5) / len(items)
        y = Y(v)
        top, bot = (y, y0) if v >= 0 else (y0, y)
        color = "#3fb950" if v >= 0 else "#f85149"
        out.append(f'<rect x="{cx-bw/2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(1,bot-top):.1f}" fill="{color}" rx="2"/>')
        if i % max(1, label_every) == 0 or i == len(items) - 1:
            out.append(f'<text x="{cx:.1f}" y="{h-26}" class="ax" text-anchor="middle">{label}</text>')
        show_val = value_labels if value_labels is not None else (len(items) <= 16)
        if show_val:
            out.append(f'<text x="{cx:.1f}" y="{(top-4) if v>=0 else (bot+12):.1f}" class="ax" text-anchor="middle" fill="{color}">{v*100:.1f}</text>')
    out.append(f'<line x1="{pad_l}" y1="{y0:.1f}" x2="{w-pad_r}" y2="{y0:.1f}" stroke="#484f58"/>')
    out.append("</svg>")
    return "".join(out)


def drawdown_series(points):
    peak = -1e18
    out = []
    for ts, eq in points:
        peak = max(peak, eq)
        out.append((ts, (eq - peak) / peak if peak > 0 else 0.0))
    return out


CSS = """
:root{--bg:#0d1117;--panel:#161b22;--border:#21262d;--text:#c9d1d9;--dim:#8b949e;--blue:#58a6ff;
--green:#3fb950;--red:#f85149;--amber:#d29922;--purple:#bc8cff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.65 -apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 22px 80px}
h1{font-size:26px;margin:0 0 6px;color:#f0f6fc;font-weight:650}
h2{font-size:18px;margin:38px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--border);color:#f0f6fc;font-weight:600}
h3{font-size:15px;margin:22px 0 8px;color:var(--blue);font-weight:600}
.sub{color:var(--dim);font-size:13px}
.tag{display:inline-block;padding:2px 9px;border-radius:11px;font-size:12px;margin-right:6px;border:1px solid}
.tag.red{color:var(--red);border-color:rgba(248,81,73,.4);background:rgba(248,81,73,.1)}
.tag.amber{color:var(--amber);border-color:rgba(210,153,34,.4);background:rgba(210,153,34,.1)}
.tag.blue{color:var(--blue);border-color:rgba(88,166,255,.4);background:rgba(88,166,255,.1)}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px 18px;margin:14px 0}
.callout{border-left:3px solid;border-radius:6px;padding:12px 16px;margin:14px 0;background:var(--panel)}
.callout.red{border-color:var(--red)} .callout.amber{border-color:var(--amber)} .callout.blue{border-color:var(--blue)}
.callout b{color:#f0f6fc}
table{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0 2px}
th,td{padding:7px 10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:600;background:#12171f;position:sticky;top:0}
tr:hover td{background:#1b212b}
td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
.pos{color:var(--green)} .neg{color:var(--red)} .muted{color:var(--dim)}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:10px;margin:8px 0}
.kv .box{background:#12171f;border:1px solid var(--border);border-radius:8px;padding:11px 13px}
.kv .k{color:var(--dim);font-size:12px;margin-bottom:3px}
.kv .v{font-size:19px;font-weight:600;font-variant-numeric:tabular-nums}
.chart{width:100%;height:auto;display:block;margin:4px 0 2px}
.ax{fill:var(--dim);font-size:11px;font-variant-numeric:tabular-nums}
.scroll{max-height:520px;overflow:auto;border:1px solid var(--border);border-radius:8px}
code{background:#12171f;padding:1px 5px;border-radius:4px;font-size:12.5px;color:var(--purple)}
.foot{margin-top:46px;padding-top:16px;border-top:1px solid var(--border);color:var(--dim);font-size:12px}
ul{margin:6px 0 6px 18px;padding:0} li{margin:3px 0}
"""


def build(data: dict, out_path: str) -> None:
    m = data["metrics"]
    meta = data["meta"]
    variants = data["variants"]
    windows = data["windows"]
    monthly = data["monthly"]
    trades = data["trades"]
    eq_sparse = data["equity_series"]
    daily = data["daily_series"]

    wins_n = round(m["win_rate"] * m["trades"])
    loss_n = m["trades"] - wins_n
    gross_loss = m["avg_loss"] * loss_n
    be_win = m["avg_loss"] / (m["avg_loss"] + m["avg_win"]) if (m["avg_loss"] + m["avg_win"]) else 0
    funding_est = m["avg_hold_hours"] / 8.0 * 0.0001 * m["avg_notional"] * m["trades"]
    open_pos = m.get("open_at_end") or {}
    is_short = m["days"] <= 45
    period_word = "本期" if is_short else "一年"
    span_word = "回测期内" if is_short else "一年下来"
    realized = m.get("realized_pnl", 0.0)
    unreal = m.get("unrealized", 0.0)
    diff_pp = (m["win_rate"] - be_win) * 100
    if diff_pp >= 0:
        tail_sentence = (
            f"实测 {m['win_rate']*100:.2f}%，<b>高出保本线 {diff_pp:.1f} 个百分点</b>，"
            f"{m['trades']} 笔已平仓交易合计 {realized:+,.2f} USDT。"
            + (f"但期末仍有 1 笔未平仓头寸浮亏 {unreal:,.2f} USDT，净值因此为 {pct(m['total_return'])}。"
               if (m.get("open_at_end") and abs(unreal) > 1e-9) else
               f"净值 {num(m['initial_capital'])} → {num(m['final_equity'])}（{pct(m['total_return'])}）。")
        )
    else:
        tail_sentence = (
            f"实测只有 {m['win_rate']*100:.2f}%，<b>差 {abs(diff_pp):.1f} 个百分点</b>，不足以覆盖手续费；"
            f"{m['trades']} 笔已平仓交易合计 {realized:+,.2f} USDT，"
            f"净值 {num(m['initial_capital'])} → {num(m['final_equity'])}（{pct(m['total_return'])}）。"
        )
    period_label = f"近 {m['days']:.0f} 天" if is_short else "近一年"
    pf_now = m["profit_factor"]
    if pf_now < 1 and m["total_return"] < 0:
        verdict = "是<b>负期望</b>的"
        verdict_short = "负期望"
        verdict_cls = "red"
    elif pf_now >= 1 and m["total_return"] >= 0:
        verdict = "是<b>正期望</b>的"
        verdict_short = "正期望"
        verdict_cls = "green"
    else:
        verdict = "呈现<b>「已平仓盈利、净值被未平仓头寸拖累」的背离</b>"
        verdict_short = "已平仓盈利但被持仓拖累"
        verdict_cls = "amber"
    sample_note = (
        f"本报告仅 {m['days']:.0f} 天、{m['trades']} 笔，样本量小，统计噪声大，只能说明这一段行情的表现，不能外推成长期结论；"
        f"长期口径请对照近一年报告（1141 笔 / -66.51% / PF 0.83）。"
        if is_short else
        "一年期样本只覆盖一轮牛熊切换，不代表未来；策略本身按 README 建议应每季度重训。"
    )

    svg_eq = line_chart(eq_sparse, 1100, 330, baseline=m["initial_capital"],
                        color="#f85149" if m["total_return"] < 0 else "#3fb950",
                        fill="rgba(248,81,73,0.08)" if m["total_return"] < 0 else "rgba(63,185,80,0.10)")
    svg_dd = line_chart(drawdown_series(daily), 1100, 220, color="#d29922",
                        fill="rgba(210,153,34,0.12)", y_fmt=lambda v: f"{v*100:.0f}%")
    daily_rets = []
    for i in range(1, len(daily)):
        prev = daily[i - 1][1]
        if prev > 0:
            daily_rets.append((daily[i][0], daily[i][1] / prev - 1))
    if m["days"] <= 45 and daily_rets:
        svg_month = bar_chart(
            [(ts_date(ts)[5:], r) for ts, r in daily_rets], 1100, 260,
            label_every=max(1, len(daily_rets) // 8), value_labels=len(daily_rets) <= 16,
        )
        period_title = f"每日收益（{len(daily_rets)} 个自然日，UTC 收盘结算）"
        period_note = ""
    else:
        svg_month = bar_chart(monthly, 1100, 240)
        period_title = "月度收益"
        period_note = ""

    # 短窗口的统计显著性提示
    if m["days"] <= 45 and len(daily_rets) > 2:
        mean_r = sum(r for _, r in daily_rets) / len(daily_rets)
        var = sum((r - mean_r) ** 2 for _, r in daily_rets) / (len(daily_rets) - 1)
        sd_r = math.sqrt(var)
        se_sharpe = 1.0 / math.sqrt(max(1, len(daily_rets))) * math.sqrt(365)
        sig_note = (f"本报告只有 {len(daily_rets)} 个日收益样本：年化 Sharpe 的抽样标准误约 ±{se_sharpe:.2f}，"
                    f"因此 Sharpe {m['sharpe']:.2f} 在统计上<b>不显著</b>；Calmar 与 CAGR 同样受样本长度制约，"
                    f"只能作为方向参考，不能当作年化业绩。")
    else:
        sig_note = ""

    var_rows = []
    for key, label, note in [
        ("zero_fee", "0 手续费（理论净信号）", "验证信号本身是否有正期望"),
        ("maker_2bp", "Maker 0.02% 双边（全部限价单）", "限价单未必成交，实盘最乐观场景"),
        ("taker_5bp", "Taker 0.05% 双边（本次主口径）", "与服务器上 007 实例一致：市价单"),
        ("taker_5bp_slip2bp", "Taker 0.05% + 滑点 2bp/边", "ETH 永续小仓位现实滑点"),
        ("taker_5bp_slip5bp", "Taker 0.05% + 滑点 5bp/边", "流动性较差时段"),
    ]:
        v = variants.get(key)
        if not v:
            continue
        cls = "neg" if v["total_return"] < 0 else "pos"
        var_rows.append(
            f"<tr><td>{label}<div class='muted' style='font-size:12px'>{note}</div></td>"
            f"<td class='r {cls}'>{pct(v['total_return'])}</td>"
            f"<td class='r'>{pct(v['mdd'])}</td><td class='r'>{v['profit_factor']:.3f}</td>"
            f"<td class='r'>{pct(v['win_rate'],1)}</td><td class='r'>{v['sharpe']:.2f}</td>"
            f"<td class='r'>{num(v['fees_total'],0)}</td></tr>"
        )

    win_rows = []
    # 本期窗口若不在下面的参照窗口里（如 20 天报告），先补一行本报告主口径
    if all(abs(m["days"] - d) > 2 for d in (30, 131, 365, 417)):
        cls = "neg" if m["total_return"] < 0 else "pos"
        win_rows.append(
            f"<tr><td><b>本期（本报告）</b><div class='muted' style='font-size:12px'>{m['start_date']} ~ {m['end_date']}</div></td>"
            f"<td class='r'>{m['days']:.0f}</td><td class='r'>{m['trades']}</td>"
            f"<td class='r {cls}'><b>{pct(m['total_return'])}</b></td><td class='r'>{pct(m['cagr'])}</td>"
            f"<td class='r'>{pct(m['mdd'])}</td><td class='r'>{m['sharpe']:.2f}</td>"
            f"<td class='r'>{m['sortino']:.2f}</td><td class='r'>{m['calmar']:.2f}</td>"
            f"<td class='r'>{pct(m['win_rate'],1)}</td><td class='r'>{m['profit_factor']:.2f}</td></tr>"
        )
    for key, label in [("30d", "近 30 天"), ("131d", "近 131 天"), ("365d", "近 365 天"), ("full", "全样本 417 天")]:
        v = windows.get(key)
        if not v:
            continue
        cls = "neg" if v["total_return"] < 0 else "pos"
        win_rows.append(
            f"<tr><td>{label}<div class='muted' style='font-size:12px'>{v['start_date']} ~ {v['end_date']}</div></td>"
            f"<td class='r'>{v['days']:.0f}</td><td class='r'>{v['trades']}</td>"
            f"<td class='r {cls}'>{pct(v['total_return'])}</td><td class='r'>{pct(v['cagr'])}</td>"
            f"<td class='r'>{pct(v['mdd'])}</td><td class='r'>{v['sharpe']:.2f}</td>"
            f"<td class='r'>{v['sortino']:.2f}</td><td class='r'>{v['calmar']:.2f}</td>"
            f"<td class='r'>{pct(v['win_rate'],1)}</td><td class='r'>{v['profit_factor']:.2f}</td></tr>"
        )

    month_rows = []
    for label, r in monthly:
        cls = "pos" if r >= 0 else "neg"
        month_rows.append(f"<tr><td>{label}</td><td class='r {cls}'>{pct(r,2)}</td></tr>")

    trade_rows = []
    for i, t in enumerate(trades, 1):
        cls = "pos" if t["net_pnl"] >= 0 else "neg"
        side = "多" if t["side"] == "LONG" else "空"
        trade_rows.append(
            f"<tr><td class='r muted'>{i}</td><td>{side}</td>"
            f"<td>{t['entry_dt']}</td><td>{t['exit_dt']}</td>"
            f"<td class='r'>{t['hold_bars']*0.25:.1f}</td>"
            f"<td class='r'>{t['entry_avg']:,.2f}</td><td class='r'>{t['exit_avg']:,.2f}</td>"
            f"<td class='r'>{t['notional']:,.0f}</td>"
            f"<td class='r'>{t['gross_pnl']:+,.2f}</td><td class='r muted'>{t['fees']:.2f}</td>"
            f"<td class='r {cls}'>{t['net_pnl']:+,.2f}</td><td>{t['reason']}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>007 ETH AlphaEvolve 15m 回测报告（{m["start_date"]} ~ {m["end_date"]}）</title>
<style>{CSS}</style></head><body><div class="wrap">

<h1>007 ETH AI 择时策略 · 回测报告<span style="font-size:15px;color:var(--dim);font-weight:400"> · {m["start_date"]} ~ {m["end_date"]}（{m["days"]:.0f} 天）</span></h1>
<div class="sub">
AlphaEvolve GP + Q-State · ETH-USDT-SWAP 永续 · 15m 信号 / 1m 止盈止损巡检 ·
回测区间 <b>{m['start_date']} ~ {m['end_date']}</b>（{m['days']:.0f} 天，{m['bars']:,} 根 15m K 线）<br>
信号实现与线上 <code>smc_eth_007_live.py</code> 为同一份代码 · 报告生成于 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
</div>

<div style="margin:14px 0 0">
<span class="tag {'red' if m['total_return']<0 else 'green'}">净值 {m['total_return']*100:+.2f}%</span>
<span class="tag {'red' if m['profit_factor']<1 else 'blue'}">盈亏比 PF {m['profit_factor']:.3f}（{'&lt; 1，负期望' if m['profit_factor']<1 else '≥ 1，已平仓口径为正'})</span>
<span class="tag amber">保本需胜率 {be_win*100:.1f}%，实测 {m['win_rate']*100:.1f}%</span>
<span class="tag blue">手续费吃掉 {m['fees_total']/m['initial_capital']*100:.0f}% 初始资金</span>
</div>

<div class="callout red">
<b>结论先说：这套 Pine 口径的 007 策略在{period_label}的真实数据上{verdict}。</b>
胜率看着很高（{pct(m['win_rate'],1)}，{wins_n} 胜 / {loss_n} 负），但单笔结构是「小赚大亏」：
平均盈利 {num(m['avg_win'])} USDT、平均亏损 {num(m['avg_loss'])} USDT，赚一笔只有亏一笔的
<b>{m['win_loss_ratio']:.2f} 倍</b>，因此需要 <b>{be_win*100:.1f}%</b> 的胜率才能保本。{tail_sentence}
（累计手续费 {num(m['fees_total'],0)} USDT，累计名义成交 {m['turnover_notional']/1e6:.2f} 百万 USDT ≈ 初始资金的 {m['turnover_notional']/m['initial_capital']:.0f} 倍）
</div>

<h2>零、手续费与成本口径</h2>
<div class="card">
<table>
<tr><th>项目</th><th>取值</th><th class="r">说明</th></tr>
<tr><td>Maker 费率</td><td>0.02%（2 bp）</td><td class="r">限价单挂单成交；本策略<b>未</b>使用（全为市价单）</td></tr>
<tr><td>Taker 费率</td><td><b>0.05%（5 bp）</b></td><td class="r">市价单吃单；本报告主口径，与线上实例一致</td></tr>
<tr><td>计费基数</td><td>开仓 / 平仓<b>名义价值</b></td><td class="r">名义价值 = 张数 × ctVal（0.1 ETH）× 成交价</td></tr>
<tr><td>杠杆关系</td><td>10x 全仓（cross）</td><td class="r">保证金 = 名义价值 / 10；<b>手续费按名义价值算，不按保证金算</b></td></tr>
<tr><td>单笔示例</td><td>名义 5,000 USDT</td><td class="r">开仓 taker = 5,000 × 0.05% = <b>2.50 USDT</b>；开平一轮 = 5.00 USDT（保证金仅 500 USDT，占保证金 1.0%）</td></tr>
<tr><td>仓位口径</td><td>首仓 50% / 加仓 75%</td><td class="r">均按「可用现金 × 比例」的名义价值，峰值 87.5% 权益（占 10x 保证金 8.75%）</td></tr>
<tr><td>累计手续费</td><td class="neg">{num(m['fees_total'])} USDT</td><td class="r">= 初始资金的 {m['fees_total']/m['initial_capital']*100:.1f}% · 累计名义成交 {m['turnover_notional']/1e6:.2f}M USDT</td></tr>
<tr><td>滑点</td><td>主口径 0 bp</td><td class="r">另列 2bp / 5bp 敏感性（见下）</td></tr>
<tr><td>资金费率</td><td class="muted">未计入</td><td class="r">平均持仓 {m['avg_hold_hours']:.1f}h，估算影响约 {funding_est:,.0f} USDT（{"本期" if is_short else "每年"}，约初始资金 {funding_est/m['initial_capital']*100:.1f}%），符号随多空与费率方向变化</td></tr>
</table>
</div>

<h2>一、综合业绩基准指标</h2>
<div class="kv">
  <div class="box"><div class="k">交易起止日期</div><div class="v" style="font-size:15px">{m['trade_first']} ~ {m['trade_last']}</div></div>
  <div class="box"><div class="k">初始资金</div><div class="v">{num(m['initial_capital'])} <span style="font-size:12px" class="muted">USDT</span></div></div>
  <div class="box"><div class="k">期末资金</div><div class="v neg">{num(m['final_equity'])} <span style="font-size:12px" class="muted">USDT</span></div></div>
  <div class="box"><div class="k">累计总收益率</div><div class="v neg">{pct(m['total_return'])}</div></div>
  <div class="box"><div class="k">年化复合收益率 (CAGR)</div><div class="v neg">{pct(m['cagr'])}</div></div>
  <div class="box"><div class="k">最大历史回撤 (Max DD)</div><div class="v neg">{pct(m['mdd'])}</div></div>
  <div class="box"><div class="k">夏普比率 (Sharpe, 年化)</div><div class="v neg">{m['sharpe']:.2f}</div></div>
  <div class="box"><div class="k">索提诺比率 (Sortino)</div><div class="v neg">{m['sortino']:.2f}</div></div>
  <div class="box"><div class="k">卡尔玛比率 (Calmar)</div><div class="v neg">{m['calmar']:.2f}</div></div>
  <div class="box"><div class="k">交易总笔数</div><div class="v">{m['trades']} <span style="font-size:12px" class="muted">笔（期末仍有 1 笔持仓）</span></div></div>
  <div class="box"><div class="k">平均胜率 (Win Rate)</div><div class="v">{pct(m['win_rate'],2)}</div></div>
  <div class="box"><div class="k">盈亏比 (Profit Factor)</div><div class="v neg">{m['profit_factor']:.3f}</div></div>
</div>
<div class="card">
<b>盈亏比解读：</b>平均盈利单 <b class="pos">{num(m['avg_win'])} USDT</b> 只有平均亏损单
<b class="neg">{num(m['avg_loss'])} USDT</b> 的 <b>{m['win_loss_ratio']:.2f} 倍</b>，
Profit Factor = 总盈利 {num(m['avg_win']*wins_n,0)} / 总亏损 {num(gross_loss,0)} = <b class="neg">{m['profit_factor']:.3f}</b>。
呈现出典型的 <b>「高频小赚 + 低频大亏」</b> 结构：止盈只要 +0.90%，止损却是 -2.50%，赔率固定为 1 : 2.78。
{'本窗口 PF ≥ 1，已平仓交易合计 <b class="pos">' + f"{realized:+,.2f}" + ' USDT</b>，胜率刚好越过保本线；' if m['profit_factor'] >= 1 else '靠 ' + f"{m['win_rate']*100:.1f}%" + ' 的胜率无法覆盖这一赔率；'}
其中未平仓头寸浮盈亏 <b class="{'pos' if m.get('unrealized',0)>=0 else 'neg'}">{unreal:+,.2f} USDT</b> 计入期末权益。
</div>

<h3>权益曲线（{m['start_date']} ~ {m['end_date']}，逐 8 小时采样）</h3>
{svg_eq}

<h3>回撤曲线（日频，峰值回撤 {pct(m['mdd'])}，{m['mdd_start']} → {m['mdd_end']}）</h3>
{svg_dd}

<h3>{period_title}</h3>
{svg_month}

<h2>二、分窗口表现</h2>
<div class="card">
<table>
<tr><th>窗口</th><th class="r">天数</th><th class="r">交易笔数</th><th class="r">累计收益</th><th class="r">CAGR</th>
<th class="r">最大回撤</th><th class="r">Sharpe</th><th class="r">Sortino</th><th class="r">Calmar</th>
<th class="r">胜率</th><th class="r">PF</th></tr>
{''.join(win_rows)}
</table>
<div class="muted" style="margin-top:8px">注：近 30 天与近 131 天、近 365 天同样为负，说明亏损不是单一行情窗口造成的，而是交易结构（赔率 1:2.78 + 高换手手续费）在全样本上稳定输钱。{sig_note}</div>
</div>

<h2>三、成本敏感性</h2>
<div class="card">
<table>
<tr><th>场景</th><th class="r">累计收益</th><th class="r">最大回撤</th><th class="r">PF</th><th class="r">胜率</th><th class="r">Sharpe</th><th class="r">手续费合计</th></tr>
{''.join(var_rows)}
</table>
<div class="muted" style="margin-top:8px">
零手续费时 PF {variants['zero_fee']['profit_factor']:.3f}、收益 {pct(variants['zero_fee']['total_return'])} —— 说明
<b>信号本身接近零期望（{"本窗口略正" if variants['zero_fee']['total_return']>0 else "略负"}）</b>，而 {num(m['fees_total'],0)} USDT 手续费把接近打平的策略拖成 {pct(m['total_return'])}。
换手率是核心问题：{period_word} {m['trades']} 笔、平均每笔名义 {num(m['avg_notional'],0)} USDT，累计名义成交 {m['turnover_notional']/1e6:.2f}M USDT。
</div>
</div>

<h2>四、交易结构拆解</h2>
<div class="card">
<table>
<tr><th>维度</th><th class="r">数值</th><th>说明</th></tr>
<tr><td>止盈 / 止损笔数</td><td class="r">{m['tp_count']} / {m['sl_count']}</td><td>止盈率 {m['tp_count']/m['trades']*100:.1f}%（每 {m['trades']/(m['sl_count'] or 1):.2f} 笔出现 1 次止损）</td></tr>
<tr><td>平均持仓时长</td><td class="r">{m['avg_hold_hours']:.1f} 小时</td><td>约 {m['avg_hold_hours']/24:.1f} 天，跨约 {m['avg_hold_hours']/8:.1f} 个资金费周期</td></tr>
<tr><td>平均名义价值</td><td class="r">{num(m['avg_notional'],0)} USDT</td><td>峰值 {num(m['peak_notional'],0)} USDT（= 初始资金 87.5%）</td></tr>
<tr><td>多单</td><td class="r">{m['long_trades']} 笔</td><td class="{'neg' if m['long_pnl']<0 else 'pos'}">盈亏 {num(m['long_pnl'])} USDT · 胜率 {pct(m['long_win'],1)}</td></tr>
<tr><td>空单</td><td class="r">{m['short_trades']} 笔</td><td class="{'neg' if m['short_pnl']<0 else 'pos'}">盈亏 {num(m['short_pnl'])} USDT · 胜率 {pct(m['short_win'],1)}</td></tr>
<tr><td>最大连胜 / 连亏</td><td class="r">{m['max_consec_win']} / {m['max_consec_loss']}</td><td>连亏上限低，因此「连亏3笔熔断」在回测中几乎不会触发</td></tr>
<tr><td>最佳 / 最差单笔</td><td class="r">+{num(m['best_trade'])} / {num(m['worst_trade'])}</td><td>单笔波动远大于平均水平</td></tr>
<tr><td>日波动率（年化）</td><td class="r">{pct(m['daily_vol'])}</td><td>净值曲线剧烈波动，Sharpe {m['sharpe']:.2f}</td></tr>
<tr><td>期末未平仓</td><td class="r">{open_pos.get('side','—')}</td><td>按最后收盘价 {num(open_pos.get('mark_px',0))} 盯市，浮盈亏 {num(open_pos.get('unrealized',0))} USDT</td></tr>
</table>
</div>

<h2>五、与仓库既有说法的对照（重要）</h2>
<div class="card">
<table>
<tr><th>指标</th><th class="r">README 说法（近一年 / 469 笔）</th><th class="r">本次实测（Pine 口径 / {m['trades']} 笔）</th><th>差异原因</th></tr>
<tr><td>平仓胜率</td><td class="r">86.35%</td><td class="r">{pct(m['win_rate'])}</td><td rowspan="4">README 的回测用的是 <code>logs/alphaevolve_15m_final_trades.json</code> 里那棵 GP 演化的 AST 信号树，
不是 <code>ETH_AI_Timing_AlphaEvolve_15m.pine</code>。两者是<b>两套不同的策略</b>。</td></tr>
<tr><td>盈亏比 PF</td><td class="r">0.87</td><td class="r">{m['profit_factor']:.2f}</td></tr>
<tr><td>平均盈利 / 平均亏损</td><td class="r">+83.44 / -605.23</td><td class="r">+{num(m['avg_win'])} / {num(m['avg_loss'])}</td></tr>
<tr><td>净值结果</td><td class="r">年化大回撤</td><td class="r">{pct(m['total_return'])}</td></tr>
</table>
<div class="callout amber" style="margin-top:12px">
<b>那棵 AST 信号树为什么不能直接实盘？</b>
<ol style="margin:6px 0 0 18px">
<li>它依赖 <code>taker_imb = (2×taker_buy_volume − volume) / volume</code>，即<b>主动买入量</b>。
OKX 的 15m K 线接口只给 open/high/low/close/vol/volCcy/volCcyQuote，<b>不提供 taker 主动买量</b>，实盘算不出来。</li>
<li>它的信号在回测里做了 <b>全样本 z-score 归一化</b>（<code>(sig−mean)/std</code>，mean/std 取自整段回测数据），
用到了未来信息；实盘只能滚动归一化，阈值 ±1.3 的意义完全不同。</li>
</ol>
因此线上只能实现 Pine 里这套只用 OHLCV 的公式。本报告测的就是线上真正会执行的那一套。
</div>
</div>

<h2>六、方法与局限</h2>
<div class="card">
<b>数据</b>
<ul>
<li>OKX <code>ETH-USDT-SWAP</code> 永续 15m，共 40,000 根（2025-08-29 17:45 UTC ~ 2026-10-20 09:30 UTC），直接取自 OKX <code>/api/v5/market/history-candles</code>。</li>
<li>数据审计：间隔全部为 15 分钟（0 处缺口）、无零价/负价、无重复时间戳。</li>
</ul>
<b>信号</b>
<ul>
<li><code>q_val = 0.88·q_val[-1] + 0.12·(k_pos·15 + hl_spread·0.8)</code>；<code>signal = Zscore20(close) + (±0.3, 当 q_val &gt; +0.05 / &lt; −0.05)</code>；开多 <code>&gt; +1.20</code>，开空 <code>&lt; −1.20</code>。</li>
<li>代码与实盘模块 <code>AlphaEvolveSignal</code> 为同一份实现（<code>backtest_007_pine.py</code> 直接 import）。</li>
<li>注意：<code>q_val</code> 的奖励项 <code>k_pos·15 + hl_spread·0.8</code> 恒为非负，所以 <code>q_val</code> 永远 &gt; 0，
「−0.3 惩罚」分支实际退化为不可达，多空门槛不对称（多：Z&gt;0.9；空：Z&lt;−1.5），策略结构性偏多。</li>
</ul>
<b>成交假设</b>
<ul>
<li>信号在 15m 收盘确认后按收盘价市价成交；加仓在同一根 K 线不重复触发。</li>
<li>止盈/止损按盘中最高/最低价触及即成交，成交价用触发价（TP = 均价×1.009，SL = 均价×0.975）。</li>
<li>同一根 15m K 线同时触及 TP 与 SL 时按 <b>TP 优先</b> → 对结果略偏乐观；线上用 1m K 线巡检，会更接近实际先到者。</li>
<li>不加仓后重复入场、不反手；期末未平仓按最后收盘价盯市，不强制平仓。</li>
</ul>
<b>未纳入</b>
<ul>
<li>资金费率（估算量级见上表）、交易所强平/保证金不足、极端行情下的滑点跳变、下单拒单与网络延迟。</li>
<li>{sample_note}</li>
</ul>
</div>

<h2>七、逐笔交易明细（{m['trades']} 笔，全部）</h2>
<div class="scroll">
<table>
<thead><tr><th class="r">#</th><th>方向</th><th>开仓 (UTC)</th><th>平仓 (UTC)</th><th class="r">持仓h</th>
<th class="r">开仓均价</th><th class="r">平仓价</th><th class="r">名义 USDT</th><th class="r">毛利</th>
<th class="r">手续费</th><th class="r">净利</th><th>出场</th></tr></thead>
<tbody>{''.join(trade_rows)}</tbody>
</table>
</div>
<div class="muted" style="margin-top:8px">同目录另存 <code>{os.path.basename(out_path).replace('.html','')}_trades.csv</code> 便于程序化处理。</div>

<div class="foot">
数据源 OKX 永续行情 · 引擎 <code>backtest/backtest_007_pine.py</code> · 线上执行器 <code>smc_eth_007_live.py</code> ·
初始资金 {num(m['initial_capital'])} USDT（线上实例为 5,000 USDT，结果按比例缩放）<br>
本报告为历史数据回测，非投资建议；手续费/滑点/资金费率的实际取值会显著改变结论。
</div>
</div></body></html>"""

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"报告已写入 {out_path} ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/bt007rep/alpha_1y_metrics.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "alphaevolve_15m_backtest_report.html"
    with open(src) as fh:
        build(json.load(fh), dst)
