import json, time, urllib.request, datetime, os, sys

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
BASE = "https://www.okx.com/api/v5"
OUT = "/root/bt013/data"
SYMBOLS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"]
BARS = {"15m": "15m", "1h": "1H", "4h": "4H", "1d": "1Dutc"}
# 起始点：按周期预热需求留足余量（15m/1h/4h 从 2024-09-01，1d 从 2024-02-01）
START = {"15m": "2024-09-01", "1h": "2024-09-01", "4h": "2024-08-01", "1d": "2024-02-01"}
SLEEP = 0.30

def ts_ms(datestr):
    return int(datetime.datetime.strptime(datestr, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)

def get(path, params):
    q = "&".join("%s=%s" % (k, v) for k, v in params.items())
    url = BASE + path + "?" + q
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        if r.status != 200:
            raise RuntimeError("HTTP %s" % r.status)
        data = json.loads(r.read().decode())
    if data.get("code") != "0":
        raise RuntimeError("okx code=%s msg=%s" % (data.get("code"), data.get("msg")))
    return data.get("data", [])

def pull_candles(sym, label, bar, start_ms):
    rows = []
    anchor = None
    calls = 0
    while True:
        params = {"instId": sym, "bar": bar, "limit": 300}
        if anchor is not None:
            params["after"] = anchor
        data = get("/market/history-candles", params)
        calls += 1
        if not data:
            break
        rows.extend(data)
        oldest = int(data[-1][0])
        if oldest <= start_ms:
            break
        if anchor is not None and oldest >= anchor:
            break
        anchor = oldest
        time.sleep(SLEEP)
        if calls % 40 == 0:
            print("  %s %s: %d calls, %d bars, oldest=%s" % (sym, label, calls, len(rows),
                  datetime.datetime.utcfromtimestamp(oldest/1000).strftime("%Y-%m-%d")), flush=True)
    rows = [r for r in rows if int(r[0]) >= start_ms]
    rows.sort(key=lambda r: int(r[0]))
    # 去重
    seen = set()
    uniq = []
    for r in rows:
        if r[0] not in seen:
            seen.add(r[0]); uniq.append(r)
    path = os.path.join(OUT, "%s_%s.jsonl" % (sym, label))
    with open(path, "w") as f:
        for r in uniq:
            f.write(json.dumps(r) + chr(10))
    print("SAVED %s %s: %d bars, %d calls, %s -> %s" % (sym, label, len(uniq), calls,
          datetime.datetime.utcfromtimestamp(int(uniq[0][0])/1000).strftime("%Y-%m-%d") if uniq else "-",
          datetime.datetime.utcfromtimestamp(int(uniq[-1][0])/1000).strftime("%Y-%m-%d") if uniq else "-"), flush=True)
    return len(uniq)

def pull_funding(sym, start_ms):
    rows = []
    anchor = None
    calls = 0
    while True:
        params = {"instId": sym, "limit": 100}
        if anchor is not None:
            params["after"] = anchor
        data = get("/public/funding-rate-history", params)
        calls += 1
        if not data:
            break
        rows.extend(data)
        oldest = int(data[-1].get("fundingTime", data[-1].get("ts", 0)))
        if oldest <= start_ms:
            break
        if anchor is not None and oldest >= anchor:
            break
        anchor = oldest
        time.sleep(SLEEP)
    rows = [r for r in rows if int(r.get("fundingTime", 0)) >= start_ms]
    rows.sort(key=lambda r: int(r["fundingTime"]))
    path = os.path.join(OUT, "%s_funding.jsonl" % sym)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + chr(10))
    print("SAVED %s funding: %d points, %d calls" % (sym, len(rows), calls), flush=True)
    return len(rows)

def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    total = 0
    for sym in SYMBOLS:
        for label, bar in BARS.items():
            total += pull_candles(sym, label, bar, ts_ms(START[label]))
        total += pull_funding(sym, ts_ms("2024-09-01"))
    print("DONE total_bars=%d elapsed=%.1fs" % (total, time.time() - t0), flush=True)

main()
