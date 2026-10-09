#!/usr/bin/env python3
import json
import re
import subprocess
from datetime import datetime, timezone, timedelta

tz_utc8 = timezone(timedelta(hours=8))

# 1. 解析所有 docker logs，提取信号、评分、证据门控、风险率、下单、平仓事件
print("正在解析 Docker 日志中的 SMC 详细得分与风控逻辑...")
cmd = "docker logs nautilus-okx-demo 2>&1"
p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

re_ansi = re.compile(r'\x1b\[[0-9;]*m')
re_ts = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)Z")

log_signals = [] # 记录所有触发的信号及评分
log_orders = [] # 记录所有订单提交
log_fills = [] # 记录所有成交
log_exits = [] # 记录所有平仓原因

for raw_line in p.stdout:
    line = raw_line.decode('utf-8', errors='ignore')
    clean = re_ansi.sub('', line).strip()
    m_ts = re_ts.search(clean)
    if not m_ts:
        continue
    
    ts_str = m_ts.group(1)
    dt_utc = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
    dt_utc8 = dt_utc.astimezone(tz_utc8)
    
    # 提取信号评分日志:
    # [BTC-USDT-SWAP] SIGNAL: LONG | Score=70.0 | Evidential u=0.285, C=0.000 | Gate Passed: True
    # 或新日志: [BTC-USDT-SWAP] 触发交易信号: 做多 | 评分=70.0 | 认知不确定性 u=...
    if "SIGNAL:" in clean or "触发交易信号:" in clean:
        m_sym = re.search(r"\[(.*?)-USDT-SWAP\]", clean)
        m_score = re.search(r"(?:Score|评分)=([\d\.]+)", clean)
        m_u = re.search(r"[u|不确定性\s*u]=([\d\.]+)", clean)
        m_c = re.search(r"[C|冲突度\s*C]=([\d\.]+)", clean)
        m_dir = re.search(r"(?:SIGNAL:\s*(LONG|SHORT)|触发交易信号:\s*(做多|做空))", clean)
        if m_sym and m_score:
            direction = "LONG" if ("LONG" in clean or "做多" in clean) else "SHORT"
            log_signals.append({
                "time": dt_utc8,
                "symbol": m_sym.group(1),
                "direction": direction,
                "score": float(m_score.group(1)),
                "u": float(m_u.group(1)) if m_u else 0.0,
                "c": float(m_c.group(1)) if m_c else 0.0,
                "raw": clean
            })

    # 提取订单提交与风险预算:
    # [BTC-USDT-SWAP] Order SUBMITTED (id=...): BUY 226 cts | Risk Budget=$966.34 (from live equity $96633.92)
    # 或 [BTC-USDT-SWAP] 委托已提交 ... 单笔风险预算=$966.34 (基于实时净值 $96633.92)
    if "Order SUBMITTED" in clean or "委托已提交" in clean or "并发协调开仓委托已提交" in clean:
        m_sym = re.search(r"\[(.*?)-USDT-SWAP\]", clean)
        m_risk = re.search(r"(?:Risk Budget|风险预算)=?\$?([\d\.]+)", clean)
        m_eq = re.search(r"(?:equity|实时净值)\s*\$?([\d\.]+)", clean)
        m_clord = re.search(r"(?:id=|ID=)([a-zA-Z0-9_-]+)", clean)
        if m_sym:
            log_orders.append({
                "time": dt_utc8,
                "symbol": m_sym.group(1),
                "risk_budget": float(m_risk.group(1)) if m_risk else 0.0,
                "equity": float(m_eq.group(1)) if m_eq else 0.0,
                "clOrdId": m_clord.group(1) if m_clord else "",
                "raw": clean
            })

    # 提取平仓原因:
    # Submitting REDUCE_ONLY EXIT order (STOP_LOSS): SELL 226 cts (NetPos=226.0)...
    # 或 发送【只减仓】平仓市价单 (止损离场 (STOP_LOSS))
    # 或 TAKE_PROFIT
    if "REDUCE_ONLY EXIT order" in clean or "【只减仓】平仓市价单" in clean or "EXIT CONFIRMED" in clean:
        m_sym = re.search(r"\[(.*?)-USDT-SWAP\]", clean)
        reason = "TAKE_PROFIT (达到目标止盈位)" if ("TAKE_PROFIT" in clean or "止盈" in clean) else ("STOP_LOSS (触发移动ATR止损)" if ("STOP_LOSS" in clean or "止损" in clean) else "WATCHDOG_SYNC / 保护性离场")
        m_pnl = re.search(r"Trade PnL=([+-]?[\d\.]+)\s*USDT", clean)
        if m_sym:
            log_exits.append({
                "time": dt_utc8,
                "symbol": m_sym.group(1),
                "reason": reason,
                "pnl": float(m_pnl.group(1)) if m_pnl else None,
                "raw": clean
            })

print(f"日志提取完成: 捕获到 {len(log_signals)} 个信号事件, {len(log_orders)} 个开仓委托, {len(log_exits)} 个平仓事件")

with open('/root/strategy_repo/parsed_log_events.json', 'w') as f:
    json.dump({
        "signals": [{
            "time": s["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": s["symbol"],
            "direction": s["direction"],
            "score": s["score"],
            "u": s["u"],
            "c": s["c"]
        } for s in log_signals],
        "orders": [{
            "time": o["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": o["symbol"],
            "risk_budget": o["risk_budget"],
            "equity": o["equity"],
            "clOrdId": o["clOrdId"]
        } for o in log_orders],
        "exits": [{
            "time": e["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": e["symbol"],
            "reason": e["reason"],
            "pnl": e["pnl"]
        } for e in log_exits]
    }, f, indent=2)
