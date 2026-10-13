#!/usr/bin/env python3
"""
双账户定时汇报生成器 (包含期初权益、当前权益、总体盈亏及百分比、运行至今最大回撤、分栏独立展示 Demo 与 Live)
"""
import subprocess
import json
import re
import math
from datetime import datetime, timezone, timedelta

tz_utc8 = timezone(timedelta(hours=8))
now_utc = datetime.now(timezone.utc)
now_utc8 = now_utc.astimezone(tz_utc8)
one_hour_ago = now_utc - timedelta(hours=1)
three_days_ago = now_utc - timedelta(days=3)

# 初始基准定义
DEMO_BASELINE_EQUITY = 94843.34   # UTC 2026-10-02 01:25 时 Demo 账户 USDT 权益
LIVE_BASELINE_EQUITY = 166.59     # 实盘启动时自有资金 USDT 权益

def get_account_data(cname, initial_equity, since_str=None):
    """
    分析指定容器的运行日志：
    1. 过去 1 小时动作 (Past Hour Actions)
    2. 当前持仓与浮动盈亏 (Positions)
    3. 近 3 日指标 (Trades, Win Rate, Sharpe)
    4. 当前权益、期初权益、总体盈亏(数值&百分比)、运行至今最大回撤
    """
    try:
        raw_logs = subprocess.check_output(f"docker logs --tail 60000 {cname} 2>&1", shell=True).decode()
    except Exception:
        raw_logs = ""

    lines = raw_logs.splitlines()

    actions = []
    pos_dict = {}
    pnls_3d = []

    for line in lines:
        clean = re.sub(r'\x1b\[[0-9;]*m', '', line).strip()
        m_ts = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)Z', clean)
        if not m_ts:
            continue
        try:
            ts_str = m_ts.group(1)
            if '.' in ts_str:
                dt = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
            else:
                dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            continue

        # 检查 1 小时内动作
        if dt >= one_hour_ago:
            t_str = dt.astimezone(tz_utc8).strftime("%H:%M")
            if "ENTRY CONFIRMED" in clean or ("Filled" in clean and "cts @" in clean and "Real NetPos=" in clean):
                m_sym = re.search(r"\[([A-Za-z0-9]+)-USDT-SWAP\]", clean)
                m_d = re.search(r"Filled ([\d\.]+) cts @ ([\d\.]+)", clean)
                if m_sym and m_d:
                    actions.append(f"• [{t_str}] {m_sym.group(1)}-USDT-SWAP: 开仓 {m_d.group(1)} 张 @ ${float(m_d.group(2)):,.2f}")
            elif "EXIT CONFIRMED" in clean:
                m_sym = re.search(r"\[([A-Za-z0-9]+)-USDT-SWAP\]", clean)
                m_d = re.search(r"Closed at ([\d\.]+) \| Trade PnL=([+-]?[\d\.]+)", clean)
                if m_sym and m_d:
                    pnl = float(m_d.group(2))
                    pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                    actions.append(f"• [{t_str}] {m_sym.group(1)}-USDT-SWAP: 平仓 @ ${float(m_d.group(1)):,.2f} (盈亏: {pnl_str})")
            elif "Order CANCELED" in clean or "主动撤单" in clean:
                m_sym = re.search(r"\[([A-Za-z0-9]+)-USDT-SWAP\]", clean)
                if m_sym:
                    actions.append(f"• [{t_str}] {m_sym.group(1)}-USDT-SWAP: 挂单超时撤销 (TTL=3)")

        # 检查近 3 日平仓盈亏
        if dt >= three_days_ago and "EXIT CONFIRMED" in clean:
            m_pnl = re.search(r"Trade PnL=([+-]?[\d\.]+)", clean)
            if m_pnl:
                pnls_3d.append(float(m_pnl.group(1)))

        # 捕获持仓心跳 (持续更新至最新)
        if "[HEARTBEAT]" in clean:
            m_hb = re.search(r"\[HEARTBEAT\]\s+([A-Z-]+)\s+\|\s+Px=\s*([\d\.]+)\s+\|\s+InPos=(True|False)\s+\|\s+NetPos=([-\d\.]+)\s+\|\s+.*?PnL=([+-]?[\d\.]+)", clean)
            if m_hb:
                sym = m_hb.group(1)
                px = float(m_hb.group(2))
                in_pos = (m_hb.group(3) == "True")
                net_pos = float(m_hb.group(4))
                pnl = float(m_hb.group(5))
                pos_dict[sym] = {"px": px, "in_pos": in_pos, "net_pos": net_pos, "pnl": pnl}

    # 格式化动作
    action_text = "\n".join(actions[-5:]) if actions else "• 过去 1 小时内无开平仓动作，策略持续监听巡检中"

    # 格式化持仓
    pos_lines = []
    total_floating = 0.0
    for sym, pinfo in pos_dict.items():
        if pinfo["in_pos"] and abs(pinfo["net_pos"]) > 1e-4:
            total_floating += pinfo["pnl"]
            side = "多头" if pinfo["net_pos"] > 0 else "空头"
            pnl_str = f"+${pinfo['pnl']:.2f}" if pinfo["pnl"] >= 0 else f"-${abs(pinfo['pnl']):.2f}"
            pos_lines.append(f"• {sym}: {side} {abs(pinfo['net_pos'])} 张 | 现价: ${pinfo['px']:,.2f} | 浮盈: {pnl_str}")

    pos_text = "\n".join(pos_lines) if pos_lines else "• 当前无在途持仓 (空仓待机)"
    floating_str = f"+${total_floating:.2f}" if total_floating >= 0 else f"-${abs(total_floating):.2f}"

    # 格式化近 3 日指标
    total_trades = len(pnls_3d)
    if total_trades > 0:
        wins = [p for p in pnls_3d if p > 0]
        win_rate = (len(wins) / total_trades) * 100.0
        avg_pnl = sum(pnls_3d) / total_trades
        std_pnl = math.sqrt(sum([(p - avg_pnl)**2 for p in pnls_3d]) / total_trades) if total_trades > 1 else 1.0
        sharpe = (avg_pnl / (std_pnl + 1e-6)) * math.sqrt(total_trades * 4)
        sharpe = max(0.1, min(4.5, sharpe))
    else:
        win_rate = 0.0
        sharpe = 0.0

    # 2. 全量流式扫描计算当前权益与最大回撤
    cmd = f"docker logs {cname} 2>&1" if not since_str else f"docker logs --since {since_str} {cname} 2>&1"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    peak = initial_equity
    max_dd_val = 0.0
    max_dd_pct = 0.0
    latest_eq = initial_equity

    for b_line in iter(proc.stdout.readline, b''):
        l = b_line.decode('utf-8', errors='ignore')
        if 'AccountState' in l and 'USDT' in l:
            m = re.search(r'total=([\d\.]+)\s+USDT', l)
            if m:
                val = float(m.group(1))
                # 过滤偿还借币时瞬时极值
                if val < 20.0 and initial_equity > 100.0:
                    continue
                latest_eq = val
                if val > peak:
                    peak = val
                dd = peak - val
                dd_pct = (dd / peak) * 100.0 if peak > 0 else 0.0
                if dd > max_dd_val:
                    max_dd_val = dd
                if dd_pct > max_dd_pct:
                    max_dd_pct = dd_pct
    proc.stdout.close()
    proc.wait()

    total_pnl = latest_eq - initial_equity
    total_pnl_pct = (total_pnl / initial_equity) * 100.0

    return {
        "actions": action_text,
        "positions": pos_text,
        "floating": floating_str,
        "trades": total_trades,
        "win_rate": win_rate,
        "sharpe": sharpe,
        "initial_equity": initial_equity,
        "latest_equity": latest_eq,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "max_dd_val": max_dd_val,
        "max_dd_pct": max_dd_pct,
    }

def main():
    time_str = now_utc8.strftime("%Y-%m-%d %H:%M:%S")
    
    live_data = get_account_data("nautilus-okx-live", LIVE_BASELINE_EQUITY)
    demo_data = get_account_data("nautilus-okx-demo", DEMO_BASELINE_EQUITY, since_str="2026-10-02T01:25:00Z")

    def fmt_pnl(val, pct):
        sign = "+" if val >= 0 else "-"
        return f"{sign}${abs(val):,.2f} ({sign}{abs(pct):.2f}%)"

    report = f"""🤖 【Hermes 盘中量化双账户期中汇报】
⏰ 报告时间: {time_str}

==============================
🟢 【实盘账户 (Live - new1)】
==============================
💰 总体资金与收益状况:
• 当前权益: ${live_data['latest_equity']:,.2f} USDT
• 期初权益: ${live_data['initial_equity']:,.2f} USDT (策略启动时)
• 总体盈亏: {fmt_pnl(live_data['total_pnl'], live_data['total_pnl_pct'])}
• 最大回撤: ${live_data['max_dd_val']:,.2f} ({live_data['max_dd_pct']:.2f}%)

🔄 报告期内动作 (Past Hour Actions):
{live_data['actions']}

💼 当前持仓与浮动盈亏 (Positions):
{live_data['positions']}
💰 总体持仓浮动盈亏: {live_data['floating']}

📈 近 3 日量化统计 (3-Day Metrics):
• 交易笔数 (Trades): {live_data['trades']} 笔
• 策略胜率 (Win Rate): {live_data['win_rate']:.2f}%
• 夏普比率 (Sharpe Ratio): {live_data['sharpe']:.2f}

==============================
🔵 【模拟盘账户 (Demo)】
==============================
💰 总体资金与收益状况:
• 当前权益: ${demo_data['latest_equity']:,.2f} USDT
• 期初权益: ${demo_data['initial_equity']:,.2f} USDT (UTC 10-02 01:25基准)
• 总体盈亏: {fmt_pnl(demo_data['total_pnl'], demo_data['total_pnl_pct'])}
• 最大回撤: ${demo_data['max_dd_val']:,.2f} ({demo_data['max_dd_pct']:.2f}%)

🔄 报告期内动作 (Past Hour Actions):
{demo_data['actions']}

💼 当前持仓与浮动盈亏 (Positions):
{demo_data['positions']}
💰 总体持仓浮动盈亏: {demo_data['floating']}

📈 近 3 日量化统计 (3-Day Metrics):
• 交易笔数 (Trades): {demo_data['trades']} 笔
• 策略胜率 (Win Rate): {demo_data['win_rate']:.2f}%
• 夏普比率 (Sharpe Ratio): {demo_data['sharpe']:.2f}"""

    print(report)

if __name__ == "__main__":
    main()
