#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""007 实例上线前的凭证/账户探针（只读，不下单）。

用途：在启动 systemd 服务之前，确认 demo1 的 API Key / Secret / Passphrase 三元组
可用、交易环境（DEMO）正确、账户权益与持仓可读。全部只读接口。

用法：
  set -a; . /root/.okx-007.env; set +a
  /root/nautilus2-venv/bin/python /root/okx_007_probe.py
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

SYMBOL = os.getenv("AE_SYMBOL", "ETH-USDT-SWAP")
IS_LIVE = os.getenv("OKX_ENV", "DEMO").strip().upper() == "LIVE"
BASE = "https://www.okx.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def signed_get(path: str):
    key = os.getenv("OKX_API_KEY", "")
    secret = os.getenv("OKX_API_SECRET", "")
    phrase = os.getenv("OKX_API_PASSPHRASE", "")
    if not (key and secret and phrase):
        print("✗ 凭证不完整：OKX_API_KEY / OKX_API_SECRET / OKX_API_PASSPHRASE 必须三项齐全")
        sys.exit(2)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    sign = base64.b64encode(
        hmac.new(secret.encode(), f"{ts}GET{path}".encode(), hashlib.sha256).digest()
    ).decode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": UA,
        "OK-ACCESS-KEY": key,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": phrase,
    }
    if not IS_LIVE:
        headers["x-simulated-trading"] = "1"
    req = urllib.request.Request(BASE + path, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    print(f"环境: {'LIVE(真实资金)' if IS_LIVE else 'DEMO(模拟盘)'} | 标的: {SYMBOL}")
    print(f"API Key 指纹: {os.getenv('OKX_API_KEY','')[:8]}… (共 {len(os.getenv('OKX_API_KEY',''))} 字符)")

    bal = signed_get("/api/v5/account/balance")
    if bal.get("code") != "0":
        print(f"✗ 余额接口失败: code={bal.get('code')} msg={bal.get('msg')}")
        print("  常见原因：Passphrase 错误 / Key 属于实盘而这里用 DEMO 头 / IP 不在白名单")
        sys.exit(3)
    acct = bal["data"][0]
    print(f"✓ 认证通过 | totalEq={acct.get('totalEq')} USDT | adjEq={acct.get('adjEq')}")
    for d in acct.get("details", []):
        if d.get("ccy") == "USDT":
            print(f"  USDT: eq={d.get('eq')} availBal={d.get('availBal')} frozenBal={d.get('frozenBal')}")

    pos = signed_get(f"/api/v5/account/positions?instId={SYMBOL}")
    if pos.get("code") == "0":
        rows = pos.get("data", [])
        print(f"✓ {SYMBOL} 持仓数: {len(rows)}")
        for p in rows:
            print(f"  {p['posSide']} {p['pos']} 张 @ {p.get('avgPx')} (mgnMode={p.get('mgnMode')})")
    else:
        print(f"✗ 持仓接口失败: {pos.get('code')} {pos.get('msg')}")

    lev = signed_get(f"/api/v5/account/leverage-info?instId={SYMBOL}&mgnMode=cross")
    if lev.get("code") == "0" and lev.get("data"):
        print(f"✓ 当前杠杆: {lev['data'][0].get('lever')}x (cross)")

    print("\n结论：凭证可用，可以启动 smc-trader-007.service")


if __name__ == "__main__":
    main()
