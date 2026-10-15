"""规则漏斗诊断：找出信号稀疏在哪一层。"""
import json, os, sys, datetime
import fvg_rules

DATA = "/root/bt013/data"
CFG = {"atr_len": 10, "adx_len": 14, "adx_min": 18.0, "use_adx": True, "min_conf": 3, "cooldown": 8,
       "max_fvg_age": 120, "min_gap_atr": 0.15, "disp_mult": 1.15, "retest_ce": True,
       "sl_beyond_fvg": True, "sl_mult": 1.2, "tp1_mult": 1.8, "tp2_mult": 3.5, "trail_mult": 1.5,
       "mom_len": 12, "use_vwap": True, "use_session": True, "require_trend": True,
       "sess_start_h": 23, "sess_end_h": 12}

def load(sym, label):
    rows = []
    with open(os.path.join(DATA, "%s_%s.jsonl" % (sym, label))) as f:
        for line in f:
            r = json.loads(line)
            if len(r) > 8 and r[8] != "1":
                continue
            rows.append({"ts": int(r[0]) * 1_000_000, "o": float(r[1]), "h": float(r[2]),
                         "l": float(r[3]), "c": float(r[4]), "v": float(r[5])})
    rows.sort(key=lambda x: x["ts"])
    return rows

sym = sys.argv[1] if len(sys.argv) > 1 else "BTC-USDT-SWAP"
label = sys.argv[2] if len(sys.argv) > 2 else "15m"
d0 = sys.argv[3] if len(sys.argv) > 3 else "2024-10-01"
d1 = sys.argv[4] if len(sys.argv) > 4 else "2026-10-08"
rows = load(sym, label)
t0 = int(datetime.datetime.strptime(d0, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() * 1e9)
t1 = int(datetime.datetime.strptime(d1, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() * 1e9)
rows = [r for r in rows if t0 <= r["ts"] <= t1]
print("DIAG| bars:", len(rows), d0, "->", d1, flush=True)
ind = fvg_rules.compute(rows, CFG)
fvgs = ind["fvgs"]
print("DIAG| FVGs:", len(fvgs), "bull:", sum(1 for f in fvgs if f["dir"] == 1), flush=True)
sigs = fvg_rules.signals(ind, CFG)
print("DIAG| signals:", sum(1 for s in sigs if s), flush=True)
# 逐层漏斗（重算一遍关键门）
n = ind["n"]; o = ind["o"]; h = ind["h"]; l = ind["l"]; c = ind["c"]
sess = 0; adx_ok_n = 0; score3 = 0; retest_bars = 0; trend_ok = 0; all_ok = 0
for i in range(n):
    if not fvg_rules._in_session(ind["ts"][i], CFG):
        continue
    sess += 1
    adx = ind["adx"][i]
    if adx is None or adx < CFG["adx_min"]:
        continue
    adx_ok_n += 1
print("DIAG| bars in session:", sess, " of", n, "| session+ADX ok:", adx_ok_n, flush=True)
# 统计每层命中率
cnt = {"ema": 0, "mom": 0, "vol": 0, "vwap": 0, "adx_dir": 0}
for i in range(n):
    ema_f = ind["ema_f"][i]; ema_s = ind["ema_s"][i]; ema_sg = ind["ema_sg"][i]
    if ema_f > ema_s > ema_sg and c[i] > ema_f: cnt["ema"] += 1
    m = ind["mom"][i]
    if m is not None and m > 0 and ind["mom"][i - 1] is not None and m > ind["mom"][i - 1]: cnt["mom"] += 1
    if ind["delta"][i] > 0 and ind["delta_ma"][i] > 0 and (ind["obv_slope"][i] or 0) > 0: cnt["vol"] += 1
    if ind["vwap"][i] is not None and c[i] > ind["vwap"][i]: cnt["vwap"] += 1
    if ind["adx"][i] is not None and ind["adx"][i] >= CFG["adx_min"] and ind["pdi"][i] > ind["mdi"][i]: cnt["adx_dir"] += 1
print("DIAG| layer hits (bull):", cnt, flush=True)
rv = [i for i, f in enumerate(fvgs) if f.get("retest_bar") is not None]
print("DIAG| FVGs with retest:", len(rv), " filled:", sum(1 for f in fvgs if f["filled"]), flush=True)
