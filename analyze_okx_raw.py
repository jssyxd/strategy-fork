#!/usr/bin/env python3
import json
from datetime import datetime, timezone, timedelta

tz_utc8 = timezone(timedelta(hours=8))

with open('/root/strategy_repo/okx_api_fills_raw.json') as f:
    fills = json.load(f)

print(f"Total raw fills: {len(fills)}")

# 打印最早和最晚的成交记录样本
fills.sort(key=lambda x: int(x['ts']))

earliest = fills[0]
latest = fills[-1]

earliest_dt = datetime.fromtimestamp(int(earliest['ts']) / 1000, tz=timezone.utc).astimezone(tz_utc8)
latest_dt = datetime.fromtimestamp(int(latest['ts']) / 1000, tz=timezone.utc).astimezone(tz_utc8)

print(f"Earliest fill: {earliest_dt.strftime('%Y-%m-%d %H:%M:%S')} | {earliest.get('instId')} | {earliest.get('side')} | {earliest.get('fillSz')} @ {earliest.get('fillPx')}")
print(f"Latest fill:   {latest_dt.strftime('%Y-%m-%d %H:%M:%S')} | {latest.get('instId')} | {latest.get('side')} | {latest.get('fillSz')} @ {latest.get('fillPx')}")

# 查看字段
sample = fills[0]
print("Keys:", list(sample.keys()))
print("Sample:", {k: sample[k] for k in ['instId', 'side', 'posSide', 'fillSz', 'fillPx', 'fee', 'feeCcy', 'ts', 'clOrdId', 'ordId', 'execType'] if k in sample})
