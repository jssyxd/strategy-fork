"""013 fvg_confluence 规则引擎（纯函数、因果、无依赖）。

对齐 BACKTEST_SPEC.md v2.2 第一节；行号指向 公允价值缺口.txt。
所有指标在第 t 根只使用 <= t 的数据，保证无未来函数。
"""
import datetime


def ema_series(xs, n):
    a = 2.0 / (n + 1.0)
    out = []
    e = None
    for x in xs:
        e = x if e is None else e + a * (x - e)
        out.append(e)
    return out


def rma_series(xs, n):
    a = 1.0 / n
    out = []
    e = None
    for x in xs:
        e = x if e is None else e + (x - e) / n
        out.append(e)
    return out


def sma_at(xs, i, n):
    if i + 1 < n:
        return None
    return sum(xs[i + 1 - n:i + 1]) / float(n)


def stdev_at(xs, i, n):
    if i + 1 < n:
        return None
    seg = xs[i + 1 - n:i + 1]
    m = sum(seg) / n
    return (sum((x - m) ** 2 for x in seg) / n) ** 0.5


def linreg_at(ys, i, n):
    """least-squares value at the last point of the window ending at i."""
    if i + 1 < n:
        return None
    y = ys[i + 1 - n:i + 1]
    xm = (n - 1) / 2.0
    ym = sum(y) / n
    num = sum((k - xm) * (y[k] - ym) for k in range(n))
    den = sum((k - xm) ** 2 for k in range(n))
    slope = (num / den) if den else 0.0
    return ym - slope * xm + slope * (n - 1)


def atr_series(h, l, c, n):
    tr = []
    for i in range(len(c)):
        if i == 0:
            tr.append(h[i] - l[i])
        else:
            tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    return rma_series(tr, n)


def adx_series(h, l, c, n):
    pdi = [None] * len(c); mdi = [None] * len(c); adx = [None] * len(c)
    st = sp = sn = None
    dxs = []
    for i in range(len(c)):
        tr = (h[i] - l[i]) if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        if i == 0:
            st, sp, sn = tr, 0.0, 0.0
        else:
            up = h[i] - h[i - 1]; dn = l[i - 1] - l[i]
            pdm = up if (up > dn and up > 0) else 0.0
            ndm = dn if (dn > up and dn > 0) else 0.0
            st = st + (tr - st) / n
            sp = sp + (pdm - sp) / n
            sn = sn + (ndm - sn) / n
        p = 100.0 * sp / st if st else 0.0
        m = 100.0 * sn / st if st else 0.0
        pdi[i] = p; mdi[i] = m
        dx = 100.0 * abs(p - m) / (p + m) if (p + m) else 0.0
        dxs.append(dx)
    a = None
    for i, dx in enumerate(dxs):
        a = dx if a is None else a + (dx - a) / n
        adx[i] = a
    return pdi, mdi, adx


def compute(bars, cfg):
    """bars: list of dict(ts,o,h,l,c,v) 按时间升序。返回 dict of 数组 + 信号。"""
    n = len(bars)
    o = [b["o"] for b in bars]; h = [b["h"] for b in bars]
    l = [b["l"] for b in bars]; c = [b["c"] for b in bars]
    v = [b["v"] for b in bars]; ts = [b["ts"] for b in bars]
    ema_f = ema_series(c, 8); ema_s = ema_series(c, 21); ema_sg = ema_series(c, 50)
    atr = atr_series(h, l, c, cfg["atr_len"])
    pdi, mdi, adx = adx_series(h, l, c, cfg["adx_len"])
    # 量差 / OBV
    bull_vol = []; bear_vol = []
    for i in range(n):
        rng = h[i] - l[i]
        bv = v[i] * (c[i] - l[i]) / rng if rng else v[i] * 0.5
        bull_vol.append(bv); bear_vol.append(v[i] - bv)
    bv_ema = ema_series(bull_vol, 14); br_ema = ema_series(bear_vol, 14)
    delta = [bv_ema[i] - br_ema[i] for i in range(n)]
    delta_ma = ema_series(delta, 5)
    obv = []
    acc = 0.0
    for i in range(n):
        if i and c[i] > c[i - 1]:
            acc += v[i]
        elif i and c[i] < c[i - 1]:
            acc -= v[i]
        obv.append(acc)
    obv_slope = [None] * n
    for i in range(n):
        if i >= 10:
            obv_slope[i] = obv[i] - obv[i - 10]
    # VWAP（UTC 日界重置）
    vwap = [None] * n
    day = None; pv = 0.0; vv = 0.0
    for i in range(n):
        d = datetime.datetime.utcfromtimestamp(ts[i] / 1e9).date()
        if d != day:
            day = d; pv = 0.0; vv = 0.0
        tp = (h[i] + l[i] + c[i]) / 3.0
        pv += tp * v[i]; vv += v[i]
        vwap[i] = pv / vv if vv else None
    # Squeeze 动量
    mom = [None] * n
    src = []
    for i in range(n):
        if i >= cfg["mom_len"] - 1:
            hh = max(h[i + 1 - cfg["mom_len"]:i + 1]); ll = min(l[i + 1 - cfg["mom_len"]:i + 1])
            sm = sma_at(c, i, cfg["mom_len"])
            base = ((hh + ll) / 2.0 + sm) / 2.0
            src.append(c[i] - base)
            mom[i] = linreg_at(src, len(src) - 1, cfg["mom_len"])
    # FVG（body 均值用前缀和，避免 O(n^2)）
    body = [abs(c[k] - o[k]) for k in range(n)]
    pref = [0.0] * (n + 1)
    for k in range(n):
        pref[k + 1] = pref[k] + body[k]
    fvgs = []
    for i in range(2, n):
        avg_body = ((pref[i + 1] - pref[i + 1 - 14]) / 14.0) if i + 1 >= 14 else None
        if avg_body is None or atr[i] is None:
            continue
        disp = abs(c[i - 1] - o[i - 1]) >= avg_body * cfg["disp_mult"]
        if not disp:
            continue
        if l[i] > h[i - 2] and (l[i] - h[i - 2]) >= cfg["min_gap_atr"] * atr[i]:
            fvgs.append({"dir": 1, "top": l[i], "btm": h[i - 2], "left": i - 2, "detect_bar": i, "filled": False, "fill_bar": None, "retest_bar": None})
        if h[i] < l[i - 2] and (l[i - 2] - h[i]) >= cfg["min_gap_atr"] * atr[i]:
            fvgs.append({"dir": -1, "top": l[i - 2], "btm": h[i], "left": i - 2, "detect_bar": i, "filled": False, "fill_bar": None, "retest_bar": None})
    return {"o": o, "h": h, "l": l, "c": c, "v": v, "ts": ts, "ema_f": ema_f, "ema_s": ema_s, "ema_sg": ema_sg,
            "atr": atr, "pdi": pdi, "mdi": mdi, "adx": adx, "delta": delta, "delta_ma": delta_ma,
            "obv_slope": obv_slope, "vwap": vwap, "mom": mom, "fvgs": fvgs, "n": n}


def signals(ind, cfg):
    """逐根产出信号与入场位。只维护活跃缺口（上限 max_fvgs，对应 Pine 的 trimFvgs）。"""
    n = ind["n"]; o = ind["o"]; h = ind["h"]; l = ind["l"]; c = ind["c"]; ts = ind["ts"]
    fvgs = ind["fvgs"]
    max_fvgs = cfg.get("max_fvgs", 40)
    out = [None] * n
    active = []
    fi = 0
    last_bull = -10 ** 9; last_bear = -10 ** 9
    prev_setup_bull = False; prev_setup_bear = False
    for i in range(n):
        while fi < len(fvgs) and fvgs[fi]["detect_bar"] <= i:
            active.append(fvgs[fi]); fi += 1
            if len(active) > max_fvgs:
                active.pop(0)
        keep = []
        for f in active:
            if f["left"] >= i:
                keep.append(f); continue
            if f["dir"] == 1 and l[i] <= f["btm"]:
                f["filled"] = True; f["fill_bar"] = i
            elif f["dir"] == -1 and h[i] >= f["top"]:
                f["filled"] = True; f["fill_bar"] = i
            if not f["filled"]:
                keep.append(f)
        active = keep
        best = {1: None, -1: None}
        for f in active:
            if f["filled"] or f["left"] >= i:
                continue
            if i - f["left"] > cfg["max_fvg_age"]:
                continue
            mid = (f["top"] + f["btm"]) / 2.0
            if not (l[i] <= f["top"] and h[i] >= f["btm"]):
                continue
            if f["dir"] == 1:
                rej = (c[i] > o[i]) and (c[i] >= mid if cfg["retest_ce"] else c[i] >= f["btm"])
            else:
                rej = (c[i] < o[i]) and (c[i] <= mid if cfg["retest_ce"] else c[i] <= f["top"])
            if not rej:
                continue
            b = best[f["dir"]]
            if b is None or f["left"] > b["left"]:
                best[f["dir"]] = f
        if best[1]: best[1]["retest_bar"] = i
        if best[-1]: best[-1]["retest_bar"] = i
        ema_f = ind["ema_f"][i]; ema_s = ind["ema_s"][i]; ema_sg = ind["ema_sg"][i]
        ema_bull = ema_f > ema_s and ema_s > ema_sg and c[i] > ema_f
        ema_bear = ema_f < ema_s and ema_s < ema_sg and c[i] < ema_f
        mom = ind["mom"][i]; mom_p = ind["mom"][i - 1] if i else None
        mom_bull = mom is not None and mom > 0 and (mom_p is not None and mom > mom_p)
        mom_bear = mom is not None and mom < 0 and (mom_p is not None and mom < mom_p)
        obv_sl = ind["obv_slope"][i]
        vol_bull = ind["delta"][i] > 0 and ind["delta_ma"][i] > 0 and (obv_sl is not None and obv_sl > 0)
        vol_bear = ind["delta"][i] < 0 and ind["delta_ma"][i] < 0 and (obv_sl is not None and obv_sl < 0)
        vw = ind["vwap"][i]
        vwap_bull = (not cfg["use_vwap"]) or (vw is not None and c[i] > vw)
        vwap_bear = (not cfg["use_vwap"]) or (vw is not None and c[i] < vw)
        adx = ind["adx"][i]
        adx_ok = (not cfg["use_adx"]) or (adx is not None and adx >= cfg["adx_min"])
        adx_bull = (not cfg["use_adx"]) or (adx_ok and ind["pdi"][i] > ind["mdi"][i])
        adx_bear = (not cfg["use_adx"]) or (adx_ok and ind["mdi"][i] > ind["pdi"][i])
        score_bull = int(ema_bull) + int(mom_bull) + int(vol_bull) + int(vwap_bull) + int(adx_bull)
        score_bear = int(ema_bear) + int(mom_bear) + int(vol_bear) + int(vwap_bear) + int(adx_bear)
        in_sess = (not cfg["use_session"]) or _in_session(ts[i], cfg)
        cool_bull = (i - last_bull) >= cfg["cooldown"]
        cool_bear = (i - last_bear) >= cfg["cooldown"]
        trend_bull = (not cfg["require_trend"]) or (ema_f > ema_s)
        trend_bear = (not cfg["require_trend"]) or (ema_f < ema_s)
        setup_bull = bool(best[1]) and score_bull >= cfg["min_conf"] and adx_ok and in_sess and cool_bull and trend_bull
        setup_bear = bool(best[-1]) and score_bear >= cfg["min_conf"] and adx_ok and in_sess and cool_bear and trend_bear
        sig_bull = setup_bull and not prev_setup_bull
        sig_bear = setup_bear and not prev_setup_bear
        prev_setup_bull, prev_setup_bear = setup_bull, setup_bear
        if sig_bull: last_bull = i
        if sig_bear: last_bear = i
        if sig_bull or sig_bear:
            d = 1 if sig_bull else -1
            f = best[d]
            sl_base = (f["btm"] if d == 1 else f["top"]) if cfg["sl_beyond_fvg"] else (l[i] if d == 1 else h[i])
            out[i] = {"dir": d, "bar": i, "sl_base": sl_base, "fvg_left": f["left"],
                      "score": score_bull if d == 1 else score_bear, "atr": ind["atr"][i],
                      "close_at_signal": c[i]}
    return out


def _in_session(ts_ns, cfg):
    dt = datetime.datetime.utcfromtimestamp(ts_ns / 1e9)
    hour = dt.hour + dt.minute / 60.0
    a, b = cfg["sess_start_h"], cfg["sess_end_h"]
    if a <= b:
        return a <= hour < b
    return hour >= a or hour < b
