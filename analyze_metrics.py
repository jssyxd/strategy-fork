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

# 数据结构
fills = []
exits = []
account_states = []
bars_count = 0
first_time = None
last_time = None

# 正则
# 2026-10-07T06:26:22.968919128Z
re_ansi = re.compile(r'\x1b\[[0-9;]*m')
re_ts = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)Z")

# 提取
for raw_line in p.stdout:
    line = raw_line.decode('utf-8', errors='ignore')
    clean = re_ansi.sub('', line).strip()
    m_ts = re_ts.search(clean)
    if not m_ts:
        continue
    
    ts_str = m_ts.group(1)
    dt_utc = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
    dt_utc8 = dt_utc.astimezone(tz_utc8)
    
    if first_time is None:
        first_time = dt_utc8
    last_time = dt_utc8
    
    # Account balance updates
    if "Updated AccountState" in clean and "OKX-DEMO-001" in clean:
        m_bal = re.search(r"AccountBalance\(total=([\d\.]+)\s+USDT.*?free=([\d\.]+)\s+USDT", clean)
        if m_bal:
            tot = float(m_bal.group(1))
            fre = float(m_bal.group(2))
            account_states.append((dt_utc8, tot, fre))
            
    # ENTRY CONFIRMED ON_ORDER_FILLED
    if "ENTRY CONFIRMED ON_ORDER_FILLED" in clean or "Filled" in clean and "cts @" in clean:
        m_sym = re.search(r"\[(.*?)-USDT-SWAP\]", clean)
        m_detail = re.search(r"Filled ([\d\.]+) cts @ ([\d\.]+)", clean)
        if m_sym and m_detail:
            fills.append({
                "time": dt_utc8,
                "type": "ENTRY",
                "symbol": m_sym.group(1),
                "qty": float(m_detail.group(1)),
                "price": float(m_detail.group(2)),
            })
            
    # EXIT CONFIRMED ON_ORDER_FILLED
    # [BTC-USDT-SWAP] >>> EXIT CONFIRMED ON_ORDER_FILLED: Closed at 85275.60 | Trade PnL=1129.95 USDT | Total PnL=1729.95 USDT <<<
    if "EXIT CONFIRMED ON_ORDER_FILLED" in clean:
        m_sym = re.search(r"\[(.*?)-USDT-SWAP\]", clean)
        m_detail = re.search(r"Closed at ([\d\.]+) \| Trade PnL=([+-]?[\d\.]+) USDT", clean)
        if m_sym and m_detail:
            exits.append({
                "time": dt_utc8,
                "symbol": m_sym.group(1),
                "price": float(m_detail.group(1)),
                "pnl": float(m_detail.group(2)),
            })
            fills.append({
                "time": dt_utc8,
                "type": "EXIT",
                "symbol": m_sym.group(1),
                "qty": 0.0,
                "price": float(m_detail.group(1)),
                "pnl": float(m_detail.group(2)),
            })

print(f"解析完成:")
print(f"首个时间: {first_time}")
print(f"最后时间: {last_time}")
print(f"账户状态更新次数: {len(account_states)}")
print(f"成交 (fills) 笔数: {len(fills)}")
print(f"已完成平仓 (exits) 笔数: {len(exits)}")

# 将详细数据打印出几条确认
if account_states:
    print(f"初始总权益: {account_states[0][1]} USDT (@ {account_states[0][0]})")
    print(f"最终总权益: {account_states[-1][1]} USDT (@ {account_states[-1][0]})")

for i, x in enumerate(exits[:5]):
    print(f"Exit {i+1}: {x['time']} | {x['symbol']} | PnL: {x['pnl']} USDT")
if len(exits) > 5:
    for i, x in enumerate(exits[-5:]):
        print(f"Exit {len(exits)-5+i+1}: {x['time']} | {x['symbol']} | PnL: {x['pnl']} USDT")
