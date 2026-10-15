#!/usr/bin/env python3
"""SMC Matrix 交易服务巡检 (health inspector).

分层检查：进程层 / 连接层 / 仓位层 / 委托层 / 资金层 / 资源层。
默认执行安全自愈动作（仅撤销超龄挂单），其余只报告。
用法: smc_health.py [--no-heal] [--json]
退出码: 0=全部正常, 1=有 WARN, 2=有 FAIL
"""
from __future__ import annotations

import json, os, re, subprocess, sys, time, urllib.request, urllib.error, hmac, hashlib, base64
from datetime import datetime, timezone, timedelta

LOG = "/root/live.log"
HEALTH_DIR = "/root/health"
ENV_FILE = "/root/.okx.env"
UNIT = "smc-trader"
SYMBOLS = ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "BNB-USDT-SWAP"]
# 阈值
ORDER_STALE_MIN = 60        # 挂单存活超过此分钟数视为孤儿（策略自身 45 分钟撤单）
HEARTBEAT_STALE_MIN = 10    # 心跳超过此分钟数视为策略卡死
MARGIN_MIN_USDT = 20.0      # 可用保证金下限
RSS_MAX_MB = 600            # 进程内存上限
DISK_MIN_GB = 2.0           # 磁盘剩余下限
LOG_MAX_MB = 200            # 日志轮转阈值
HISTORY_MAX_MB = 10         # 巡检历史上限，超过只保留最近 2000 条
ERROR_WINDOW_MIN = 20       # 统计最近多少分钟的错误

results: list[tuple[str, str, str]] = []   # (level, name, detail)
def rec(level, name, detail=""):
    results.append((level, name, detail))

def sh(cmd: str) -> str:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as e:
        return f"__ERR__{e}"

# ─── 引信: OKX 只读调用 ───────────────────────────────────────────────────────
def load_env():
    env = {}
    for line in open(ENV_FILE, encoding="utf-8"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
    return env

def okx_get(path, env):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond//1000:03d}Z"
    sign = base64.b64encode(hmac.new(env["OKX_API_SECRET"].encode(),
        (ts + "GET" + path).encode(), hashlib.sha256).digest()).decode()
    h = {"OK-ACCESS-KEY": env["OKX_API_KEY"], "OK-ACCESS-SIGN": sign, "OK-ACCESS-TIMESTAMP": ts,
         "OK-ACCESS-PASSPHRASE": env["OKX_API_PASSPHRASE"], "Content-Type": "application/json",
         "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}
    try:
        with urllib.request.urlopen(urllib.request.Request("https://www.okx.com" + path, headers=h), timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"code": "NETERR", "msg": str(e)}

# ─── A. 进程层 ────────────────────────────────────────────────────────────────
def check_process():
    state = sh(f"systemctl is-active {UNIT}")
    if state != "active":
        rec("FAIL", "service", f"{UNIT} 状态={state}")
        return None
    pid = sh(f"systemctl show -p MainPID --value {UNIT}")
    n_restart = sh(f"systemctl show -p NRestarts --value {UNIT}")
    rss_kb = sh(f"ps -o rss= -p {pid} 2>/dev/null").strip()
    rss_mb = int(rss_kb) / 1024 if rss_kb.isdigit() else -1
    n_inst = sh('pgrep -fc "[s]mc_live_trader_live.py"')
    rec("OK", "service", f"active pid={pid} restarts={n_restart} rss={rss_mb:.0f}MB")
    if rss_mb > RSS_MAX_MB:
        rec("WARN", "mem_rss", f"进程内存 {rss_mb:.0f}MB 超过 {RSS_MAX_MB}MB")
    if n_inst.isdigit() and int(n_inst) != 1:
        rec("FAIL", "instance", f"检测到 {n_inst} 个交易进程实例（应为 1）")
    return pid

# ─── B. 连接层 ────────────────────────────────────────────────────────────────
def check_connectivity(env):
    cfg = okx_get("/api/v5/account/config", env)
    if cfg.get("code") != "0":
        rec("FAIL", "okx_api", f"只读接口异常 code={cfg.get('code')} msg={str(cfg.get('msg'))[:60]}")
    else:
        rec("OK", "okx_api", f"uid={cfg['data'][0].get('uid')} acctLv={cfg['data'][0].get('acctLv')}")
    pat = r"60031\|60006\|APIKey does not match"
    errs = sh(f"awk -v d=\"$(date -u -d '{ERROR_WINDOW_MIN} min ago' +%Y-%m-%dT%H:%M)\" '$0>=d' {LOG} 2>/dev/null | grep -cE '{pat}'")
    if errs.isdigit() and int(errs) > 3:
        rec("WARN", "ws_auth", f"最近 {ERROR_WINDOW_MIN} 分钟 WebSocket 认证错误 {errs} 次")

# ─── C. 仓位层 ────────────────────────────────────────────────────────────────
def parse_heartbeats():
    """返回 {symbol: (timestamp, InPos, NetPos)}"""
    out = {}
    try:
        tail = sh(f"tail -c 400000 {LOG}")
    except Exception:
        return out
    for line in tail.splitlines():
        line = re.sub(r"\x1b\[[0-9;]*m", "", line)
        m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.\d+Z.*\[HEARTBEAT\]\s+(\S+)\s+\|\s+Px=\s*([0-9.]+)\s+\|\s+InPos=(\w+)\s+\|\s+NetPos=([-0-9.]+)", line)
        if m:
            out[m.group(2)] = (m.group(1), m.group(4) == "True", float(m.group(5)))
    return out

def check_positions(env, hb):
    pos = okx_get("/api/v5/account/positions?instType=SWAP", env)
    if pos.get("code") != "0":
        rec("FAIL", "positions_query", f"持仓查询失败 {str(pos)[:80]}")
        return
    exch = {p["instId"]: float(p["pos"]) for p in pos.get("data", [])}
    now = datetime.now(timezone.utc)
    for sym in SYMBOLS:
        e = exch.get(sym, 0.0)
        if sym not in hb:
            rec("WARN", "heartbeat", f"{sym} 无心跳记录")
            continue
        ts, in_pos, net = hb[sym]
        age = (now - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)).total_seconds() / 60
        if age > HEARTBEAT_STALE_MIN:
            rec("FAIL", "heartbeat_stale", f"{sym} 心跳已 {age:.0f} 分钟未更新")
        if abs(e) > 1e-9 and not in_pos:
            rec("FAIL", "orphan_position", f"{sym} 交易所有 {e} 张持仓但策略 InPos=False（孤儿仓）")
        elif abs(e - net) > 1e-9:
            rec("WARN", "position_drift", f"{sym} 交易所 {e} 张 vs 策略 {net} 张")
    rec("OK", "positions", f"交易所持仓 {len(exch)} 个标的: " + ", ".join(f"{k}={v:g}" for k, v in exch.items()))

# ─── D. 委托层 ────────────────────────────────────────────────────────────────
def check_orders(env, heal=True):
    oo = okx_get("/api/v5/trade/orders-pending?instType=SWAP", env)
    if oo.get("code") != "0":
        rec("FAIL", "orders_query", f"挂单查询失败 {str(oo)[:80]}")
        return
    now_ms = time.time() * 1000
    pend = oo.get("data", [])
    if not pend:
        rec("OK", "orders", "无挂单")
    for o in pend:
        age_min = (now_ms - int(o.get("cTime", now_ms))) / 60000
        tag = f"{o['instId']} {o['side']} {o['sz']}张 @{o.get('px')} 存活{age_min:.0f}分钟"
        if age_min > ORDER_STALE_MIN:
            if heal:
                r = okx_cancel(o["instId"], o["ordId"], env)
                rec("WARN", "orphan_order_healed", f"{tag} → 已撤销 ({r})")
            else:
                rec("FAIL", "orphan_order", tag + " （超龄，未自愈）")
        else:
            rec("OK", "order_pending", tag)
    rej = sh(f"awk -v d=\"$(date -u -d '{ERROR_WINDOW_MIN} min ago' +%Y-%m-%dT%H:%M)\" '$0>=d' {LOG} 2>/dev/null | grep -c 'REJECTED'")
    if rej.isdigit() and int(rej) > 0:
        rec("WARN", "rejected", f"最近 {ERROR_WINDOW_MIN} 分钟有 {rej} 次下单被拒")

def okx_cancel(inst, ord_id, env):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond//1000:03d}Z"
    body = json.dumps({"instId": inst, "ordId": ord_id})
    sign = base64.b64encode(hmac.new(env["OKX_API_SECRET"].encode(),
        (ts + "POST" + "/api/v5/trade/cancel-order" + body).encode(), hashlib.sha256).digest()).decode()
    h = {"OK-ACCESS-KEY": env["OKX_API_KEY"], "OK-ACCESS-SIGN": sign, "OK-ACCESS-TIMESTAMP": ts,
         "OK-ACCESS-PASSPHRASE": env["OKX_API_PASSPHRASE"], "Content-Type": "application/json",
         "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}
    try:
        req = urllib.request.Request("https://www.okx.com/api/v5/trade/cancel-order", data=body.encode(), headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
        return f"code={d.get('code')}"
    except Exception as e:
        return f"err={e}"

# ─── E. 资金层 ────────────────────────────────────────────────────────────────
def check_funds(env):
    b = okx_get("/api/v5/account/balance", env)
    if b.get("code") != "0":
        rec("FAIL", "balance_query", str(b)[:80]); return
    d = b["data"][0]
    avail = 0.0
    for det in d.get("details", []):
        if det["ccy"] == "USDT":
            avail = float(det.get("availBal", 0))
    rec("OK", "balance", f"总权益 {float(d.get('totalEq', 0)):.2f} USD | 可用 {avail:.2f} USDT")
    if avail < MARGIN_MIN_USDT:
        rec("WARN", "margin_low", f"可用保证金 {avail:.2f} USDT 低于阈值 {MARGIN_MIN_USDT}")

# ─── F. 资源层 ────────────────────────────────────────────────────────────────
def check_resources():
    df = sh("df -BG --output=avail / | tail -1").replace("G", "")
    if df.isdigit() and float(df) < DISK_MIN_GB:
        rec("FAIL", "disk", f"根分区剩余 {df}GB 低于 {DISK_MIN_GB}GB")
    else:
        rec("OK", "disk", f"根分区剩余 {df}GB")
    log_mb = os.path.getsize(LOG) / 1048576 if os.path.exists(LOG) else 0
    if log_mb > LOG_MAX_MB:
        rec("WARN", "log_size", f"日志 {log_mb:.0f}MB 超过 {LOG_MAX_MB}MB，建议轮转")
    else:
        rec("OK", "log_size", f"日志 {log_mb:.1f}MB")


# ─── 自检模式：用合成数据验证每个告警分支 ─────────────────────────────────────
def run_selftest():
    global okx_get, okx_cancel, parse_heartbeats
    cancelled = []
    now_ms = int(time.time() * 1000)
    fake_pending = [{"instId": "ETH-USDT-SWAP", "side": "sell", "sz": "1", "px": "2586.95",
                     "ordId": "FAKE_ORD_1", "cTime": str(now_ms - 2 * 3600 * 1000)}]

    def fake_get(path, env):
        if "account/config" in path:
            return {"code": "0", "data": [{"uid": "selftest", "acctLv": "2"}]}
        if "positions" in path:
            return {"code": "0", "data": [{"instId": "BNB-USDT-SWAP", "pos": "38", "avgPx": "771.4"},
                                        {"instId": "SOL-USDT-SWAP", "pos": "-4", "avgPx": "116.4"}]}
        if "orders-pending" in path:
            return {"code": "0", "data": fake_pending}
        if "balance" in path:
            return {"code": "0", "data": [{"totalEq": "100", "details": [{"ccy": "USDT", "availBal": "5"}]}]}
        return {"code": "0", "data": [{}]}

    def fake_cancel(inst, oid, env):
        cancelled.append((inst, oid))
        return "code=0"

    def fake_hb():
        old = (datetime.now(timezone.utc) - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
        hb = {s: (old, False, 0.0) for s in SYMBOLS}
        hb["SOL-USDT-SWAP"] = (old, True, 0.0)   # 交易所 -4 张 vs 策略记录 0 张 -> drift
        return hb

    okx_get, okx_cancel, parse_heartbeats = fake_get, fake_cancel, fake_hb
    env = load_env()
    check_connectivity(env)
    check_positions(env, parse_heartbeats())
    check_orders(env, heal=True)
    check_funds(env)

    names = {n for _, n, _ in results}
    expect = {"orphan_order_healed", "orphan_position", "heartbeat_stale", "position_drift", "margin_low", "okx_api"}
    missing = expect - names
    print("=== 自检：合成异常数据 ===")
    icon = {"OK": "✓", "WARN": "⚠", "FAIL": "✗"}
    for lv, n, d in results:
        print(f"  {icon[lv]} {lv:4s} {n:22s} {d[:80]}")
    print()
    print("命中分支:", sorted(names & expect))
    print("撤销调用:", cancelled)
    ok = not missing and cancelled == [("ETH-USDT-SWAP", "FAKE_ORD_1")]
    print("SELFTEST:", "PASS" if ok else f"FAIL missing={sorted(missing)}")
    return 0 if ok else 1

# ─── 主流程 ───────────────────────────────────────────────────────────────────
def main():
    if "--selftest" in sys.argv:
        return run_selftest()
    heal = "--no-heal" not in sys.argv
    as_json = "--json" in sys.argv
    env = load_env()
    check_process()
    check_connectivity(env)
    hb = parse_heartbeats()
    check_positions(env, hb)
    check_orders(env, heal=heal)
    check_funds(env)
    check_resources()

    worst = "OK"
    for lv, _, _ in results:
        if lv == "FAIL": worst = "FAIL"
        elif lv == "WARN" and worst != "FAIL": worst = "WARN"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(HEALTH_DIR, exist_ok=True)
    payload = {"ts": ts, "worst": worst, "checks": [{"level": l, "name": n, "detail": d} for l, n, d in results]}
    with open(f"{HEALTH_DIR}/latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    hist = f"{HEALTH_DIR}/history.log"
    if os.path.exists(hist) and os.path.getsize(hist) > HISTORY_MAX_MB * 1048576:
        with open(hist, encoding="utf-8") as f:
            keep = f.readlines()[-2000:]
        with open(hist, "w", encoding="utf-8") as f:
            f.writelines(keep)
    with open(hist, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        icon = {"OK": "✓", "WARN": "⚠", "FAIL": "✗"}
        print(f"[{ts}] 巡检结果: {worst}")
        for lv, n, d in results:
            print(f"  {icon[lv]} {lv:4s} {n:20s} {d}")
    return {"OK": 0, "WARN": 1, "FAIL": 2}[worst]

if __name__ == "__main__":
    sys.exit(main())
