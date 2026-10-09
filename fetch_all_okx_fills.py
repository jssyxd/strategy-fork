#!/usr/bin/env python3
import hmac
import base64
import json
import time
import urllib.request
from datetime import datetime, timezone, timedelta

# 读取凭证
env = {}
with open('/opt/nautilus/.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

API_KEY = env.get('OKX_API_KEY')
API_SECRET = env.get('OKX_API_SECRET')
PASSPHRASE = env.get('OKX_API_PASSPHRASE')

def okx_request(method, request_path, body=""):
    now = datetime.now(timezone.utc)
    timestamp = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    message = timestamp + method.upper() + request_path + body
    mac = hmac.new(API_SECRET.encode('utf-8'), message.encode('utf-8'), digestmod='sha256')
    sign = base64.b64encode(mac.digest()).decode('utf-8')
    
    url = "https://www.okx.com" + request_path
    headers = {
        'OK-ACCESS-KEY': API_KEY,
        'OK-ACCESS-SIGN': sign,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': PASSPHRASE,
        'x-simulated-trading': '1',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0'
    }
    
    req = urllib.request.Request(url, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))

all_fills = []
# 分页拉取 fills-history
# OKX 游标分页: after 参数表示请求比该 billId/fillId 更早的数据
last_bill_id = None
endpoint = '/api/v5/trade/fills-history?instType=SWAP&limit=100'

while True:
    path = endpoint
    if last_bill_id:
        path += f"&after={last_bill_id}"
    
    res = okx_request('GET', path)
    data = res.get('data', [])
    if not data:
        break
    
    all_fills.extend(data)
    print(f"Fetched {len(data)} fills, total: {len(all_fills)}, oldest ts: {data[-1].get('ts')}")
    
    if len(data) < 100:
        break
    last_bill_id = data[-1].get('billId')
    time.sleep(0.2)

# 也拉一下近 3 天的 fills 避免有遗漏
try:
    res_recent = okx_request('GET', '/api/v5/trade/fills?instType=SWAP&limit=100')
    recent_data = res_recent.get('data', [])
    existing_ids = {f.get('fillId') or f.get('billId') for f in all_fills}
    added = 0
    for f in recent_data:
        fid = f.get('fillId') or f.get('billId')
        if fid not in existing_ids:
            all_fills.append(f)
            added += 1
    print(f"Added {added} fills from recent trade/fills endpoint")
except Exception as e:
    print("Recent fills error:", e)

# 保存原始 API 数据
with open('/root/strategy_repo/okx_api_fills_raw.json', 'w') as f:
    json.dump(all_fills, f, indent=2)

print(f"Total fills retrieved from OKX API: {len(all_fills)}")
