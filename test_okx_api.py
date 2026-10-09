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
    # OKX 要求 ISO 格式时间戳，如 2020-12-08T09:08:57.715Z
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
        'x-simulated-trading': '1',  # Demo 模拟盘必须带这个 header
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0'
    }
    
    req = urllib.request.Request(url, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))

# 测试接口: 获取最近 3 个月成交历史 /api/v5/trade/fills-history
# 或 /api/v5/trade/fills (近3天)
# 或 /api/v5/trade/orders-history (历史订单)
try:
    res = okx_request('GET', '/api/v5/trade/fills?instType=SWAP&limit=100')
    print("trade/fills code:", res.get('code'), "msg:", res.get('msg'), "len:", len(res.get('data', [])))
    
    res_hist = okx_request('GET', '/api/v5/trade/fills-history?instType=SWAP&limit=100')
    print("trade/fills-history code:", res_hist.get('code'), "msg:", res_hist.get('msg'), "len:", len(res_hist.get('data', [])))

    res_orders = okx_request('GET', '/api/v5/trade/orders-history-archive?instType=SWAP&limit=100')
    print("orders-history-archive code:", res_orders.get('code'), "msg:", res_orders.get('msg'), "len:", len(res_orders.get('data', [])))
except Exception as e:
    print("OKX API Error:", e)
