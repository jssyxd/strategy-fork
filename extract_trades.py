#!/usr/bin/env python3
import re
import math
import subprocess
from datetime import datetime, timezone, timedelta

tz_utc8 = timezone(timedelta(hours=8))

# 获取所有 docker logs
print("正在读取 Docker 日志...")
cmd = "docker logs nautilus-okx-demo 2>&1"
p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

re_ansi = re.compile(r'\x1b\[[0-9;]*m')
re_ts = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)Z")

trades = []
hourly_equity = {}
all_equity_points = []
bars_processed = 0

open_trades = {} # symbol -> {entry_time, side, qty, entry_px}

for raw_line in p.stdout:
    line = raw_line.decode('utf-8', errors='ignore')
    clean = re_ansi.sub('', line).strip()
    m_ts = re_ts.search(clean)
    if not m_ts:
        continue
    
    ts_str = m_ts.group(1)
    dt_utc = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
    dt_utc8 = dt_utc.astimezone(tz_utc8)
    
    # 提取账户状态
    if "Updated AccountState" in clean and "OKX-DEMO-001" in clean:
        m_bal = re.search(r"AccountBalance\(total=([\d\.]+)\s+USDT,\s+locked=([\d\.]+)\s+USDT,\s+free=([\d\.]+)\s+USDT", clean)
        if m_bal:
            tot = float(m_bal.group(1))
            lck = float(m_bal.group(2))
            fre = float(m_bal.group(3))
            all_equity_points.append({
                "time": dt_utc8,
                "total": tot,
                "locked": lck,
                "free": fre
            })
            # 按小时聚合
            hr_key = dt_utc8.strftime("%Y-%m-%d %H:00")
            hourly_equity[hr_key] = {
                "time_str": hr_key,
                "dt": dt_utc8,
                "total": tot,
                "locked": lck,
                "free": fre
            }
            
    # 开仓成交确认
    # >>> ENTRY CONFIRMED ON_ORDER_FILLED: Filled 226.0 cts @ 85199.30 | Real NetPos=226.0 ...
    if "ENTRY CONFIRMED ON_ORDER_FILLED" in clean or ("Filled" in clean and "cts @" in clean and "Real NetPos=" in clean):
        m_sym = re.search(r"\[(.*?)-USDT-SWAP\]", clean)
        m_detail = re.search(r"Filled ([\d\.]+) cts @ ([\d\.]+) \| Real NetPos=([-\d\.]+)", clean)
        if m_sym and m_detail:
            sym = m_sym.group(1)
            qty = float(m_detail.group(1))
            px = float(m_detail.group(2))
            net_pos = float(m_detail.group(3))
            side = "多头" if net_pos > 0 else "空头"
            open_trades[sym] = {
                "entry_time": dt_utc8,
                "side": side,
                "qty": qty,
                "entry_px": px
            }

    # 平仓成交确认
    # >>> EXIT CONFIRMED ON_ORDER_FILLED: Closed at 85275.60 | Trade PnL=1129.95 USDT | Total PnL=1729.95 USDT <<<
    if "EXIT CONFIRMED ON_ORDER_FILLED" in clean or ("Closed at" in clean and "Trade PnL=" in clean):
        m_sym = re.search(r"\[(.*?)-USDT-SWAP\]", clean)
        m_detail = re.search(r"Closed at ([\d\.]+) \| Trade PnL=([+-]?[\d\.]+) USDT", clean)
        if m_sym and m_detail:
            sym = m_sym.group(1)
            close_px = float(m_detail.group(1))
            pnl = float(m_detail.group(2))
            
            ot = open_trades.get(sym, {})
            entry_time = ot.get("entry_time", dt_utc8)
            entry_px = ot.get("entry_px", 0.0)
            side = ot.get("side", "做多" if pnl > 0 and close_px > entry_px else "未知")
            qty = ot.get("qty", 0.0)
            
            trades.append({
                "exit_time": dt_utc8,
                "entry_time": entry_time,
                "symbol": sym,
                "side": side,
                "entry_px": entry_px,
                "close_px": close_px,
                "qty": qty,
                "pnl": pnl
            })
            if sym in open_trades:
                del open_trades[sym]

print(f"总计提取到已完成交易笔数: {len(trades)}")
print(f"总计提取到小时级权益点数: {len(hourly_equity)}")

import json
with open("/root/strategy_repo/extracted_data.json", "w") as f:
    json.dump({
        "trades": [{
            "exit_time": t["exit_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "entry_time": t["entry_time"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(t["entry_time"], datetime) else str(t["entry_time"]),
            "symbol": t["symbol"],
            "side": t["side"],
            "entry_px": t["entry_px"],
            "close_px": t["close_px"],
            "qty": t["qty"],
            "pnl": t["pnl"]
        } for t in trades],
        "hourly_equity": [{
            "time": v["time_str"],
            "total": v["total"],
            "locked": v["locked"],
            "free": v["free"]
        } for v in sorted(hourly_equity.values(), key=lambda x: x["time_str"])],
        "open_trades": [{
            "symbol": k,
            "side": v["side"],
            "qty": v["qty"],
            "entry_px": v["entry_px"],
            "entry_time": v["entry_time"].strftime("%Y-%m-%d %H:%M:%S")
        } for k, v in open_trades.items()]
    }, f, indent=2)

print("数据已成功导出至 /root/strategy_repo/extracted_data.json")
