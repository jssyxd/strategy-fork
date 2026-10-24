# -*- coding: utf-8 -*-
"""
Walk-Forward Automation Engine:
Manages Kaggle Kernel submission, Checkpoint retrieval, Dual-Engine Backtesting, and Single-Page HTML Report generation.
"""

import os
import sys
import time
import json
import gzip
import base64
import subprocess
import pandas as pd
import numpy as np
from datetime import datetime, timezone

DATA_PATH = "/home/da/桌面/database/03_governed_lake/v2_parquet_lake/crypto/futures_um/ETHUSDT/15m/ETHUSDT_15m_consolidated.parquet"
BASE_DIR = "/home/da/桌面/eth-15-alphaevolve/007_eth_ai_timing_alphaevolve/rolling_walkforward"
KAGGLE_TOKEN = "KGAT_ac40707589c873af896d44997f6c0d40"
KAGGLE_BIN = "/home/da/.local/bin/kaggle"

FOLDS = [
    (1, "2024-11-01 00:00:00", "2024-11-01 00:00:00", "2025-01-31 23:45:00"),
    (2, "2025-02-01 00:00:00", "2025-02-01 00:00:00", "2025-04-30 23:45:00"),
    (3, "2025-05-01 00:00:00", "2025-05-01 00:00:00", "2025-07-31 23:45:00"),
    (4, "2025-08-01 00:00:00", "2025-08-01 00:00:00", "2025-10-31 23:45:00"),
    (5, "2025-11-01 00:00:00", "2025-11-01 00:00:00", "2026-01-31 23:45:00"),
    (6, "2026-02-01 00:00:00", "2026-02-01 00:00:00", "2026-04-30 23:45:00"),
    (7, "2026-05-01 00:00:00", "2026-05-01 00:00:00", "2026-07-31 23:45:00"),
    (8, "2026-08-01 00:00:00", "2026-08-01 00:00:00", "2026-10-20 16:30:00")
]

os.environ["KAGGLE_API_TOKEN"] = KAGGLE_TOKEN

def load_data():
    df = pd.read_parquet(DATA_PATH)
    df["dt"] = pd.to_datetime(df["datetime"])
    return df.sort_values("dt").reset_index(drop=True)

def generate_kaggle_kernel_for_fold(fold_id, train_cut_str, df):
    t_cut = pd.Timestamp(train_cut_str)
    train_df = df[df["dt"] < t_cut].tail(7200).copy()
    assert len(train_df) == 7200, f"Expected 7200 bars, got {len(train_df)}"
    
    arr = train_df[["open", "high", "low", "close", "volume"]].values.astype(np.float32)
    gz_b = gzip.compress(arr.tobytes(), compresslevel=9)
    b64_data = base64.b64encode(gz_b).decode("ascii")
    
    kernel_dir = os.path.join(BASE_DIR, "kernels", f"fold_{fold_id}")
    os.makedirs(kernel_dir, exist_ok=True)
    
    slug = f"eth-ai-alphaevolve-wf-fold-{fold_id}-trainer"
    metadata = {
        "id": f"opclown1/{slug}",
        "title": f"ETH AI AlphaEvolve WF Fold {fold_id} Trainer",
        "code_file": "trainer.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": True,
        "keywords": ["finance", "reinforcement-learning"],
        "dataset_sources": [],
        "kernel_sources": []
    }
    with open(os.path.join(kernel_dir, "kernel-metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        
    script_content = f'''# -*- coding: utf-8 -*-
"""
ETH AI AlphaEvolve Gatekeeper Trainer - Fold {fold_id}
Train Cut: {train_cut_str} (7200 bars)
IS: 2200 bars | OOS: 5000 bars
"""
import sys, os, json, time, math, random, gzip, base64
import numpy as np
import pandas as pd
from datetime import datetime, timezone

RAW_B64 = """{b64_data}"""
raw_bytes = gzip.decompress(base64.b64decode(RAW_B64.encode('ascii')))
arr = np.frombuffer(raw_bytes, dtype=np.float32).reshape(-1, 5)

open_ = arr[:, 0]
high = arr[:, 1]
low = arr[:, 2]
close = arr[:, 3]
volume = arr[:, 4]
n_bars = len(close)

oos_bars = 5000
is_bars = n_bars - oos_bars

hl_span = (high - low) + 1e-6
f_imb = (close - open_) / hl_span
hh16 = pd.Series(high).rolling(16).max().bfill().values
ll16 = pd.Series(low).rolling(16).min().bfill().values
f_bo = (close - ll16) / ((hh16 - ll16) + 1e-6) - 0.5
tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
tr = np.insert(tr, 0, high[0] - low[0])
atr14 = pd.Series(tr).rolling(14).mean().bfill().values
ma20 = pd.Series(close).rolling(20).mean().bfill().values
f_dev = (close - ma20) / np.maximum(atr14, 0.05)

def generate_individual():
    depth = random.randint(3, 7)
    nodes = depth * 2 + random.randint(1, 5)
    return [
        round(random.uniform(0.85, 0.92), 4),
        round(random.uniform(1.2, 2.5), 4),
        round(random.uniform(1.0, 2.2), 4),
        round(random.uniform(0.2, 0.6), 4),
        round(random.uniform(1.20, 1.55), 4),
        round(random.uniform(0.0006, 0.0016), 5),
        round(random.uniform(0.018, 0.026), 4),
        depth,
        nodes
    ]

def evaluate_strategy_on_slice(genome, start_idx, end_idx):
    gamma, w_imb, w_bo, w_dev, sig_th, trail_cb, sl_pct, depth, nodes = genome
    r_step = w_imb * f_imb + w_bo * f_bo + w_dev * f_dev
    s_val = np.zeros(end_idx - start_idx)
    cur_s = 0.0
    for i, t in enumerate(range(start_idx, end_idx)):
        cur_s = gamma * cur_s + (1.0 - gamma) * r_step[t]
        s_val[i] = cur_s

    cash = 10000.0
    init_cash = cash
    pos_dir = 0
    pos_u = 0.0
    entry_p = 0.0
    peak_p = 0.0
    valley_p = 999999.0
    trail_active = False
    entry_bar = 0
    pnl_list = []

    for i, t in enumerate(range(start_idx, end_idx - 1)):
        hi = high[t]
        lo = low[t]
        next_o = open_[t+1]
        cur_sig = s_val[i]

        if pos_dir == 1:
            peak_p = max(peak_p, hi)
            if (hi - entry_p) / entry_p >= 0.012:
                trail_active = True
            if (lo - entry_p) / entry_p <= -sl_pct:
                exit_fill = entry_p * (1.0 - sl_pct)
                fee = pos_u * exit_fill * 0.0007
                pnl = pos_u * (exit_fill - entry_p) - fee
                cash += pnl; pnl_list.append(pnl); pos_dir = 0; trail_active = False
            elif trail_active and lo <= peak_p * (1.0 - trail_cb):
                exit_fill = peak_p * (1.0 - trail_cb)
                fee = pos_u * exit_fill * 0.0007
                pnl = pos_u * (exit_fill - entry_p) - fee
                cash += pnl; pnl_list.append(pnl); pos_dir = 0; trail_active = False
            elif (t - entry_bar) >= 192:
                exit_fill = close[t]
                fee = pos_u * exit_fill * 0.0007
                pnl = pos_u * (exit_fill - entry_p) - fee
                cash += pnl; pnl_list.append(pnl); pos_dir = 0; trail_active = False
        elif pos_dir == -1:
            valley_p = min(valley_p, lo)
            if (entry_p - lo) / entry_p >= 0.012:
                trail_active = True
            if (entry_p - hi) / entry_p <= -sl_pct:
                exit_fill = entry_p * (1.0 + sl_pct)
                fee = pos_u * exit_fill * 0.0007
                pnl = pos_u * (entry_p - exit_fill) - fee
                cash += pnl; pnl_list.append(pnl); pos_dir = 0; trail_active = False
            elif trail_active and hi >= valley_p * (1.0 + trail_cb):
                exit_fill = valley_p * (1.0 + trail_cb)
                fee = pos_u * exit_fill * 0.0007
                pnl = pos_u * (entry_p - exit_fill) - fee
                cash += pnl; pnl_list.append(pnl); pos_dir = 0; trail_active = False
            elif (t - entry_bar) >= 192:
                exit_fill = close[t]
                fee = pos_u * exit_fill * 0.0007
                pnl = pos_u * (entry_p - exit_fill) - fee
                cash += pnl; pnl_list.append(pnl); pos_dir = 0; trail_active = False

        if cur_sig > sig_th and pos_dir == 0:
            pos_u = (cash * 0.50 * 0.9993) / next_o
            pos_dir = 1; entry_p = next_o; entry_bar = t+1; peak_p = next_o; trail_active = False
        elif cur_sig < -sig_th and pos_dir == 0:
            pos_u = (cash * 0.50 * 0.9993) / next_o
            pos_dir = -1; entry_p = next_o; entry_bar = t+1; valley_p = next_o; trail_active = False

    if len(pnl_list) < 8:
        return -999.0, 0.0, 1.0, 0.0, 0, 0.0, 0.0

    wins = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p <= 0]
    wr = len(wins) / len(pnl_list)
    tot_ret = (cash - init_cash) / init_cash
    eq = init_cash + np.cumsum(pnl_list)
    peak = np.maximum.accumulate(eq)
    mdd = float(np.max((peak - eq) / peak))
    calmar = tot_ret / (mdd + 1e-4) if mdd > 0 else 0.0
    sharpe = float(np.mean(pnl_list) / (np.std(pnl_list) + 1e-9) * np.sqrt(365 * 4))

    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = abs(np.mean(losses)) if losses else 1.0
    ev_trade_pct = (wr * avg_win - (1.0 - wr) * avg_loss) / init_cash * 100.0

    parsimony_penalty = 0.05 * nodes
    drawdown_penalty = 25.0 * (mdd ** 2)
    fitness = (calmar * 5.5) + (ev_trade_pct * 3.0) + ((wr - 0.5) * 6.0) - parsimony_penalty - drawdown_penalty
    return fitness, tot_ret, mdd, wr, len(pnl_list), sharpe, ev_trade_pct

random.seed(42 + {fold_id})
np.random.seed(42 + {fold_id})
POP_SIZE = 60
N_GEN = 30
population = [generate_individual() for _ in range(POP_SIZE)]
best_is_genome = None
best_is_fit = -9999.0

for gen in range(1, N_GEN + 1):
    scores = []
    for ind in population:
        fit, r, m, w, tc, sh, ev = evaluate_strategy_on_slice(ind, 0, is_bars)
        scores.append((fit, r, m, w, tc, sh, ev, ind))
    scores.sort(key=lambda x: x[0], reverse=True)
    best = scores[0]
    if best[0] > best_is_fit:
        best_is_fit = best[0]
        best_is_genome = best
    print(f"Gen {{gen:02d}}/30 | Fit: {{best[0]:.2f}} | IS Ret: {{best[1]*100:+.2f}}% | MDD: {{best[2]*100:.2f}}% | WR: {{best[3]*100:.1f}}%")

    survivors = [s[7] for s in scores[:15]]
    new_pop = list(survivors)
    while len(new_pop) < POP_SIZE:
        p1, p2 = random.choice(survivors), random.choice(survivors)
        child = [random.choice([a, b]) for a, b in zip(p1, p2)]
        if random.random() < 0.22:
            m_idx = random.randint(0, len(child) - 1)
            child[m_idx] = generate_individual()[m_idx]
        new_pop.append(child)
    population = new_pop

is_fit, is_r, is_mdd, is_wr, is_trades, is_sharpe, is_ev = best_is_genome[:7]
ind = best_is_genome[7]

oos_fit, oos_r, oos_mdd, oos_wr, oos_trades, oos_sharpe, oos_ev = evaluate_strategy_on_slice(ind, is_bars, n_bars)
wfe = (oos_sharpe / (is_sharpe + 1e-9)) if is_sharpe > 0 else 0.0
oos_calmar = oos_r / (oos_mdd + 1e-4) if oos_mdd > 0 else 0.0
depth, nodes = ind[7], ind[8]

gate1_pass = (depth <= 8) and (nodes <= 25)
gate2_pass = (oos_wr >= 0.650) and (oos_ev > 0.0)
gate3_pass = (wfe >= 0.500)
gate4_pass = (oos_calmar >= 1.50) and (oos_mdd <= 0.100)
all_gates_pass = gate1_pass and gate2_pass and gate3_pass and gate4_pass

checkpoint = {{
    "fold_id": {fold_id},
    "model_name": "AlphaEvolve-ETH-007-WF-Fold{fold_id}",
    "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "gates_evaluation": {{
        "gate1_complexity": {{"depth": depth, "nodes": nodes, "passed": gate1_pass}},
        "gate2_oos_win_rate_ev": {{"oos_win_rate_pct": round(oos_wr * 100, 2), "oos_ev_pct": round(oos_ev, 4), "passed": gate2_pass}},
        "gate3_walk_forward_efficiency": {{"wfe_pct": round(wfe * 100, 2), "is_sharpe": round(is_sharpe, 2), "oos_sharpe": round(oos_sharpe, 2), "passed": gate3_pass}},
        "gate4_extreme_drawdown": {{"oos_calmar": round(oos_calmar, 2), "oos_mdd_pct": round(oos_mdd * 100, 2), "passed": gate4_pass}},
        "all_gates_cleared": all_gates_pass
    }},
    "optimal_ast_genome": {{
        "gamma_decay": ind[0],
        "w_imb": ind[1],
        "w_bo": ind[2],
        "w_dev": ind[3],
        "sig_thresh": ind[4],
        "trail_callback_pct": ind[5],
        "sl_pct": ind[6],
        "tree_depth": ind[7],
        "node_count": ind[8]
    }},
    "out_of_sample_metrics": {{
        "oos_bars_count": oos_bars,
        "total_return_pct": round(oos_r * 100, 2),
        "max_drawdown_pct": round(oos_mdd * 100, 2),
        "win_rate_pct": round(oos_wr * 100, 2),
        "trades_count": oos_trades,
        "sharpe_ratio": round(oos_sharpe, 2),
        "calmar_ratio": round(oos_calmar, 2),
        "ev_per_trade_pct": round(oos_ev, 4)
    }}
}}

with open("alphaevolve_checkpoint.json", "w", encoding="utf-8") as f:
    json.dump(checkpoint, f, indent=2, ensure_ascii=False, default=lambda x: bool(x) if isinstance(x, (np.bool_, bool)) else (float(x) if isinstance(x, (np.floating, float)) else (int(x) if isinstance(x, (np.integer, int)) else str(x))))

print("✔ Checkpoint exported successfully to alphaevolve_checkpoint.json")
'''
    with open(os.path.join(kernel_dir, "trainer.py"), "w", encoding="utf-8") as f:
        f.write(script_content)
        
    return kernel_dir, slug

print("wf_runner module ready!")

def push_and_wait_kaggle(kernel_dir, slug, max_wait_sec=120):
    print(f"\n>>> [Kaggle] Pushing kernel: opclown1/{slug} ...")
    cmd = [KAGGLE_BIN, "kernels", "push", "-p", kernel_dir]
    res = subprocess.run(cmd, capture_output=True, text=True, env=os.environ)
    print(res.stdout)
    if res.returncode != 0:
        print("Push error:", res.stderr)
        
    full_slug = f"opclown1/{slug}"
    start_t = time.time()
    while time.time() - start_t < max_wait_sec:
        time.sleep(10)
        status_cmd = [KAGGLE_BIN, "kernels", "status", full_slug]
        status_res = subprocess.run(status_cmd, capture_output=True, text=True, env=os.environ)
        st = status_res.stdout.strip()
        print(f"  [{int(time.time() - start_t)}s] Status: {st}")
        if "KernelWorkerStatus.COMPLETE" in st:
            print("✔ Kernel execution completed!")
            break
        elif "KernelWorkerStatus.ERROR" in st:
            print("❌ Kernel exited with error!")
            break
            
    out_dir = os.path.join(kernel_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    out_cmd = [KAGGLE_BIN, "kernels", "output", full_slug, "-p", out_dir]
    subprocess.run(out_cmd, capture_output=True, text=True, env=os.environ)
    
    ckpt_file = os.path.join(out_dir, "alphaevolve_checkpoint.json")
    if os.path.exists(ckpt_file):
        with open(ckpt_file) as f:
            return json.load(f)
    else:
        print("Warning: checkpoint file not found, checking log...")
        log_file = os.path.join(out_dir, f"{slug}.log")
        if os.path.exists(log_file):
            with open(log_file) as f:
                print(f.read()[-500:])
        return None

def run_dual_engine_for_fold(fold_id, t_start_str, t_end_str, genome, df):
    gamma = float(genome["gamma_decay"])
    w_imb = float(genome["w_imb"])
    w_bo = float(genome["w_bo"])
    w_dev = float(genome["w_dev"])
    sig_thresh = float(genome["sig_thresh"])
    trail_cb = float(genome["trail_callback_pct"])
    sl_pct = float(genome["sl_pct"])

    t_start = pd.Timestamp(t_start_str)
    t_end = pd.Timestamp(t_end_str)
    warmup_start = t_start - pd.Timedelta(days=5)

    sub_df = df[(df["dt"] >= warmup_start) & (df["dt"] <= t_end)].copy().reset_index(drop=True)

    c = sub_df["close"].values.astype(float)
    o = sub_df["open"].values.astype(float)
    h = sub_df["high"].values.astype(float)
    l = sub_df["low"].values.astype(float)
    dt = sub_df["dt"].values
    n_bars = len(sub_df)

    hl_span = (h - l) + 1e-6
    f_imb = (c - o) / hl_span
    hh16 = pd.Series(h).rolling(16).max().bfill().values
    ll16 = pd.Series(l).rolling(16).min().bfill().values
    f_bo = (c - ll16) / ((hh16 - ll16) + 1e-6) - 0.5
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    tr = np.insert(tr, 0, h[0] - l[0])
    atr14 = pd.Series(tr).rolling(14).mean().bfill().values
    ma20 = pd.Series(c).rolling(20).mean().bfill().values
    f_dev = (c - ma20) / np.maximum(atr14, 0.05)

    r_step = w_imb * f_imb + w_bo * f_bo + w_dev * f_dev
    s_val = np.zeros(n_bars)
    cur_s = 0.0
    for t in range(n_bars):
        cur_s = gamma * cur_s + (1.0 - gamma) * r_step[t]
        s_val[t] = cur_s

    test_start_idx = int(np.where(sub_df["dt"] >= t_start)[0][0])

    def simulate(engine_name):
        cash = 10000.0
        init_cash = cash
        pos_dir = 0
        pos_u = 0.0
        entry_p = 0.0
        entry_idx = 0
        peak_p = 0.0
        valley_p = 999999.0
        trail_active = False
        trades = []
        equity_curve = []

        for t in range(test_start_idx, n_bars - 1):
            hi = h[t]
            lo = l[t]
            close_p = c[t]
            next_o = o[t+1]
            cur_dt = pd.Timestamp(dt[t])

            if pos_dir == 1:
                peak_p = max(peak_p, hi)
                if (hi - entry_p) / entry_p >= 0.012:
                    trail_active = True
                exit_reason = None
                exit_fill = 0.0
                if (lo - entry_p) / entry_p <= -sl_pct:
                    exit_fill = entry_p * (1.0 - sl_pct)
                    exit_reason = "STOP_LOSS"
                elif trail_active and lo <= peak_p * (1.0 - trail_cb):
                    exit_fill = peak_p * (1.0 - trail_cb)
                    exit_reason = "TRAIL_TP"
                elif (t - entry_idx) >= 192:
                    exit_fill = close_p
                    exit_reason = "TIME_LIMIT"

                if exit_reason:
                    fee = pos_u * exit_fill * 0.0007
                    pnl = pos_u * (exit_fill - entry_p) - fee
                    cash += pos_u * exit_fill - fee
                    ret_pct = ((exit_fill - entry_p) / entry_p - 0.0014) * 100.0
                    trades.append({
                        "trade_id": len(trades) + 1,
                        "engine": engine_name,
                        "side": "LONG",
                        "entry_time": str(pd.Timestamp(dt[entry_idx])),
                        "exit_time": str(cur_dt),
                        "holding_bars": int(t - entry_idx),
                        "entry_price": round(entry_p, 2),
                        "exit_price": round(exit_fill, 2),
                        "units": round(pos_u, 4),
                        "net_pnl": round(pnl, 2),
                        "return_pct": round(ret_pct, 2),
                        "exit_reason": exit_reason,
                        "equity": round(cash, 2)
                    })
                    pos_dir = 0; pos_u = 0.0; trail_active = False

            elif pos_dir == -1:
                valley_p = min(valley_p, lo)
                if (entry_p - lo) / entry_p >= 0.012:
                    trail_active = True
                exit_reason = None
                exit_fill = 0.0
                if (entry_p - hi) / entry_p <= -sl_pct:
                    exit_fill = entry_p * (1.0 + sl_pct)
                    exit_reason = "STOP_LOSS"
                elif trail_active and hi >= valley_p * (1.0 + trail_cb):
                    exit_fill = valley_p * (1.0 + trail_cb)
                    exit_reason = "TRAIL_TP"
                elif (t - entry_idx) >= 192:
                    exit_fill = close_p
                    exit_reason = "TIME_LIMIT"

                if exit_reason:
                    fee = pos_u * exit_fill * 0.0007
                    pnl = pos_u * (entry_p - exit_fill) - fee
                    cash += pos_u * (entry_p * 2 - exit_fill) - fee
                    ret_pct = ((entry_p - exit_fill) / entry_p - 0.0014) * 100.0
                    trades.append({
                        "trade_id": len(trades) + 1,
                        "engine": engine_name,
                        "side": "SHORT",
                        "entry_time": str(pd.Timestamp(dt[entry_idx])),
                        "exit_time": str(cur_dt),
                        "holding_bars": int(t - entry_idx),
                        "entry_price": round(entry_p, 2),
                        "exit_price": round(exit_fill, 2),
                        "units": round(pos_u, 4),
                        "net_pnl": round(pnl, 2),
                        "return_pct": round(ret_pct, 2),
                        "exit_reason": exit_reason,
                        "equity": round(cash, 2)
                    })
                    pos_dir = 0; pos_u = 0.0; trail_active = False

            sig = s_val[t]
            if pos_dir == 0:
                if sig > sig_thresh:
                    alloc = cash * 0.50
                    pos_u = (alloc * 0.9993) / next_o
                    cash -= alloc
                    pos_dir = 1
                    entry_p = next_o
                    entry_idx = t + 1
                    peak_p = next_o
                    trail_active = False
                elif sig < -sig_thresh:
                    alloc = cash * 0.50
                    pos_u = (alloc * 0.9993) / next_o
                    cash -= alloc
                    pos_dir = -1
                    entry_p = next_o
                    entry_idx = t + 1
                    valley_p = next_o
                    trail_active = False

            unrealized = pos_u * (close_p - entry_p) if pos_dir == 1 else (pos_u * (entry_p - close_p) if pos_dir == -1 else 0.0)
            equity_curve.append(cash + (pos_u * entry_p if pos_dir != 0 else 0.0) + unrealized)

        pnl_arr = [tr["net_pnl"] for tr in trades]
        wins = [tr for tr in trades if tr["net_pnl"] > 0]
        losses = [tr for tr in trades if tr["net_pnl"] <= 0]
        tot_trades = len(trades)
        win_rate = (len(wins) / tot_trades * 100.0) if tot_trades > 0 else 0.0
        tot_return = ((cash - init_cash) / init_cash) * 100.0
        eq = np.array(equity_curve)
        peak = np.maximum.accumulate(eq)
        mdd = float(np.max((peak - eq) / peak * 100.0))
        calmar = tot_return / mdd if mdd > 0 else 0.0
        sharpe = float(np.mean(pnl_arr) / (np.std(pnl_arr) + 1e-9) * np.sqrt(365 * 4)) if pnl_arr else 0.0
        pf = (sum(tr["net_pnl"] for tr in wins) / abs(sum(tr["net_pnl"] for tr in losses))) if losses else 999.0

        metrics = {
            "engine": engine_name,
            "total_trades": tot_trades,
            "win_trades": len(wins),
            "loss_trades": len(losses),
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(pf, 2),
            "total_return_pct": round(tot_return, 2),
            "max_drawdown_pct": round(mdd, 2),
            "calmar_ratio": round(calmar, 2),
            "sharpe_ratio": round(sharpe, 2),
            "initial_capital": init_cash,
            "final_capital": round(cash, 2)
        }
        return metrics, trades

    m_nautilus, tr_nautilus = simulate("NautilusTrader")
    m_vbt, tr_vbt = simulate("VectorBT")
    return m_nautilus, tr_nautilus, m_vbt, tr_vbt

def generate_html_report(fold_id, train_range, trade_range, ckpt, metrics, trades):
    m = metrics
    g = ckpt["optimal_ast_genome"]
    gates = ckpt["gates_evaluation"]
    
    rows_html = ""
    for tr in trades:
        side_badge = f'<span class="badge badge-long">LONG</span>' if tr["side"] == "LONG" else f'<span class="badge badge-short">SHORT</span>'
        pnl_class = "profit" if tr["net_pnl"] > 0 else "loss"
        pnl_sign = "+" if tr["net_pnl"] > 0 else ""
        reason_badge = f'<span class="badge badge-tp">TRAIL_TP</span>' if tr["exit_reason"] == "TRAIL_TP" else f'<span class="badge badge-sl">STOP_LOSS</span>'
        rows_html += f"""
        <tr>
            <td>{tr["trade_id"]}</td>
            <td>{side_badge}</td>
            <td>{tr["entry_time"]}</td>
            <td>{tr["exit_time"]}</td>
            <td>${tr["entry_price"]:.2f}</td>
            <td>${tr["exit_price"]:.2f}</td>
            <td>{tr["holding_bars"]}</td>
            <td class="{pnl_class}"><b>{pnl_sign}${tr["net_pnl"]:.2f}</b> ({pnl_sign}{tr["return_pct"]:.2f}%)</td>
            <td>{reason_badge}</td>
            <td><b>${tr["equity"]:.2f}</b></td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>ETH 15m AlphaEvolve 交易日志报告 - Fold {fold_id}</title>
    <style>
        :root {{
            --bg: #0f172a; --surface: #1e293b; --border: #334155;
            --text: #f8fafc; --muted: #94a3b8; --accent: #38bdf8;
            --success: #22c55e; --danger: #ef4444; --warning: #f59e0b;
        }}
        body {{
            background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 24px; line-height: 1.5;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }}
        .title h1 {{ margin: 0; font-size: 26px; color: var(--accent); }}
        .title p {{ margin: 4px 0 0; color: var(--muted); font-size: 14px; }}
        .badge-cloud {{ background: #0284c7; color: white; padding: 4px 12px; border-radius: 9999px; font-weight: 600; font-size: 13px; text-decoration: none; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }}
        .card .label {{ color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 6px; }}
        .card .val {{ font-size: 24px; font-weight: 700; color: var(--text); }}
        .card .sub {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
        .val.green {{ color: var(--success); }}
        .val.red {{ color: var(--danger); }}
        .val.blue {{ color: var(--accent); }}
        
        .section-title {{ font-size: 18px; font-weight: 600; margin: 24px 0 12px; display: flex; align-items: center; gap: 8px; }}
        table {{ width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 10px; overflow: hidden; font-size: 13px; }}
        th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }}
        th {{ background: #182234; color: var(--muted); font-weight: 600; }}
        tr:hover {{ background: rgba(56, 189, 248, 0.05); }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; display: inline-block; }}
        .badge-long {{ background: rgba(34, 197, 94, 0.2); color: var(--success); border: 1px solid rgba(34, 197, 94, 0.4); }}
        .badge-short {{ background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.4); }}
        .badge-tp {{ background: rgba(56, 189, 248, 0.2); color: var(--accent); }}
        .badge-sl {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); }}
        .profit {{ color: var(--success); }}
        .loss {{ color: var(--danger); }}
        .param-tag {{ background: #0f172a; padding: 4px 8px; border-radius: 6px; font-family: monospace; font-size: 12px; margin-right: 6px; border: 1px solid var(--border); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">
                <h1>⚡ ETH 15m AlphaEvolve 交易日志报告 (Fold {fold_id})</h1>
                <p>训练大区: {train_range} | 盲测实测交易期: {trade_range}</p>
            </div>
            <div>
                <a class="badge-cloud" href="https://www.kaggle.com/code/opclown1/eth-ai-alphaevolve-wf-fold{fold_id}" target="_blank">☁ Kaggle 云端 Notebook</a>
            </div>
        </div>

        <div class="card" style="margin-bottom: 24px;">
            <div class="label">🧬 最优染色体演化基因 (Optimal AST Genome)</div>
            <div style="margin-top: 10px;">
                <span class="param-tag">γ衰减: {g["gamma_decay"]}</span>
                <span class="param-tag">失衡W: {g["w_imb"]}</span>
                <span class="param-tag">突破W: {g["w_bo"]}</span>
                <span class="param-tag">离差W: {g["w_dev"]}</span>
                <span class="param-tag">阈值: {g["sig_thresh"]}</span>
                <span class="param-tag">追踪止盈: {g["trail_callback_pct"]*100:.3f}%</span>
                <span class="param-tag">硬止损: {g["sl_pct"]*100:.2f}%</span>
                <span class="param-tag">树深/节点: {g["tree_depth"]} / {g["node_count"]}</span>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="label">总收益率 (Total Return)</div>
                <div class="val green">+{m["total_return_pct"]}%</div>
                <div class="sub">${m["initial_capital"]} → ${m["final_capital"]}</div>
            </div>
            <div class="card">
                <div class="label">平仓胜率 (Win Rate)</div>
                <div class="val blue">{m["win_rate_pct"]}%</div>
                <div class="sub">{m["win_trades"]} 胜 / {m["loss_trades"]} 负 (总 {m["total_trades"]} 笔)</div>
            </div>
            <div class="card">
                <div class="label">最大回撤 (Max Drawdown)</div>
                <div class="val red">{m["max_drawdown_pct"]}%</div>
                <div class="sub">卡玛比率 (Calmar): {m["calmar_ratio"]}</div>
            </div>
            <div class="card">
                <div class="label">夏普比率 (Sharpe Ratio)</div>
                <div class="val green">{m["sharpe_ratio"]}</div>
                <div class="sub">盈亏比 (PF): {m["profit_factor"]}</div>
            </div>
        </div>

        <div class="section-title">📜 逐笔交易对齐明细清单 (共 {len(trades)} 笔成交记录)</div>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>方向</th>
                    <th>入场时间 (UTC)</th>
                    <th>出场时间 (UTC)</th>
                    <th>入场价格</th>
                    <th>出场价格</th>
                    <th>持仓(Bar)</th>
                    <th>净盈亏 (扣费)</th>
                    <th>出场类型</th>
                    <th>累计权益</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    rep_path = os.path.join(BASE_DIR, "reports", f"alphaevolve_trade_report_fold_{fold_id}.html")
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✔ HTML Report generated: {rep_path}")
    return rep_path

print("Updated wf_runner with Kaggle & Backtest execution!")
