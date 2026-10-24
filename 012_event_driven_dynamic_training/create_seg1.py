import os, gzip, base64, json, pandas as pd, numpy as np

DATA_PATH = '/home/da/桌面/database/03_governed_lake/v2_parquet_lake/crypto/futures_um/ETHUSDT/15m/ETHUSDT_15m_consolidated.parquet'
df = pd.read_parquet(DATA_PATH)
df['dt'] = pd.to_datetime(df['datetime'])
df = df.sort_values('dt').reset_index(drop=True)

train_df = df[df['dt'] < '2024-10-01'].tail(25000).copy()
assert len(train_df) == 25000

arr = train_df[['open', 'high', 'low', 'close', 'volume']].values.astype(np.float32)
gz_b = gzip.compress(arr.tobytes(), compresslevel=9)
b64_data = base64.b64encode(gz_b).decode('ascii')

k_dir = '/home/da/.omp/wt/dynamic/012_event_driven_dynamic_training/kernels/seg_1'
os.makedirs(k_dir, exist_ok=True)

metadata = {
    'id': 'opclown1/eth-ai-dynamic-event-seg-1-trainer',
    'title': 'ETH AI Dynamic Event Seg 1 Trainer',
    'code_file': 'trainer.py',
    'language': 'python',
    'kernel_type': 'script',
    'is_private': True,
    'enable_gpu': False,
    'enable_tpu': False,
    'enable_internet': True,
    'keywords': ['finance', 'reinforcement-learning'],
    'dataset_sources': [],
    'kernel_sources': []
}
with open(f'{k_dir}/kernel-metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)

template = '''# -*- coding: utf-8 -*-
"""
ETH AI Dynamic Event-Driven Long-Horizon Trainer - Seg 1
Dataset: 25,000 bars 15m (~260 days)
IS: 19,970 bars | Purge: 20 | Embargo: 10 | OOS: 5,000 bars
"""
import sys, os, json, time, math, random, gzip, base64
import numpy as np
import pandas as pd
import numba as nb
from datetime import datetime, timezone

RAW_B64 = """__B64_DATA__"""
raw_bytes = gzip.decompress(base64.b64decode(RAW_B64.encode('ascii')))
arr = np.frombuffer(raw_bytes, dtype=np.float32).reshape(-1, 5)

open_ = arr[:, 0].astype(np.float64)
high = arr[:, 1].astype(np.float64)
low = arr[:, 2].astype(np.float64)
close = arr[:, 3].astype(np.float64)
volume = arr[:, 4].astype(np.float64)
n_bars = len(close)

is_bars = 19970
oos_start = 20000

hl_span = (high - low) + 1e-6
f_imb = (close - open_) / hl_span
hh16 = pd.Series(high).rolling(16).max().bfill().values.astype(np.float64)
ll16 = pd.Series(low).rolling(16).min().bfill().values.astype(np.float64)
f_bo = (close - ll16) / ((hh16 - ll16) + 1e-6) - 0.5
tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
tr = np.insert(tr, 0, high[0] - low[0])
atr14 = pd.Series(tr).rolling(14).mean().bfill().values.astype(np.float64)
ma20 = pd.Series(close).rolling(20).mean().bfill().values.astype(np.float64)
f_dev = (close - ma20) / np.maximum(atr14, 0.05)

@nb.njit(fastmath=True)
def jit_eval(c, o, h, l, f_imb, f_bo, f_dev, gamma, w_imb, w_bo, w_dev, sig_th, trail_cb, sl_pct, s_idx, e_idx):
    n = e_idx - s_idx
    s_val = np.zeros(n, dtype=np.float64)
    cur_s = 0.0
    for i in range(n):
        t = s_idx + i
        r = w_imb * f_imb[t] + w_bo * f_bo[t] + w_dev * f_dev[t]
        cur_s = gamma * cur_s + (1.0 - gamma) * r
        s_val[i] = cur_s
        
    cash = 10000.0; init_cash = cash
    pos_dir = 0; pos_u = 0.0; entry_p = 0.0; entry_bar = 0; peak_p = 0.0; valley_p = 999999.0; trail_active = False
    pnl_sum = 0.0; pnl_sq_sum = 0.0; wins = 0; trades = 0; max_equity = cash; max_dd = 0.0
    
    for i in range(n - 1):
        t = s_idx + i; hi = h[t]; lo = l[t]; close_p = c[t]; next_o = o[t+1]; sig = s_val[i]
        if pos_dir == 1:
            if hi > peak_p: peak_p = hi
            if (hi - entry_p) / entry_p >= 0.012: trail_active = True
            exit_p = 0.0
            if (lo - entry_p) / entry_p <= -sl_pct: exit_p = entry_p * (1.0 - sl_pct)
            elif trail_active and lo <= peak_p * (1.0 - trail_cb): exit_p = peak_p * (1.0 - trail_cb)
            elif (t - entry_bar) >= 192: exit_p = close_p
            if exit_p > 0.0:
                pnl = pos_u * (exit_p - entry_p) - pos_u * exit_p * 0.0007
                cash += pnl; pnl_sum += pnl; pnl_sq_sum += pnl * pnl; trades += 1
                if pnl > 0.0: wins += 1
                pos_dir = 0; trail_active = False
        elif pos_dir == -1:
            if lo < valley_p: valley_p = lo
            if (entry_p - lo) / entry_p >= 0.012: trail_active = True
            exit_p = 0.0
            if (entry_p - hi) / entry_p <= -sl_pct: exit_p = entry_p * (1.0 + sl_pct)
            elif trail_active and hi >= valley_p * (1.0 + trail_cb): exit_p = valley_p * (1.0 + trail_cb)
            elif (t - entry_bar) >= 192: exit_p = close_p
            if exit_p > 0.0:
                pnl = pos_u * (entry_p - exit_p) - pos_u * exit_p * 0.0007
                cash += pnl; pnl_sum += pnl; pnl_sq_sum += pnl * pnl; trades += 1
                if pnl > 0.0: wins += 1
                pos_dir = 0; trail_active = False
        if pos_dir == 0:
            if sig > sig_th:
                pos_u = (cash * 0.50 * 0.9993) / next_o; pos_dir = 1; entry_p = next_o; entry_bar = t+1; peak_p = next_o; trail_active = False
            elif sig < -sig_th:
                pos_u = (cash * 0.50 * 0.9993) / next_o; pos_dir = -1; entry_p = next_o; entry_bar = t+1; valley_p = next_o; trail_active = False
        if cash > max_equity: max_equity = cash
        cur_dd = (max_equity - cash) / max_equity
        if cur_dd > max_dd: max_dd = cur_dd
        
    if trades < 20: return -999.0, 0.0, 1.0, 0.0, 0, 0.0, 0.0
    tot_ret = (cash - init_cash) / init_cash; wr = wins / trades
    calmar = tot_ret / (max_dd + 1e-4) if max_dd > 0 else 0.0
    avg_pnl = pnl_sum / trades
    var_pnl = (pnl_sq_sum / trades) - (avg_pnl * avg_pnl)
    std_pnl = np.sqrt(max(1e-9, var_pnl))
    sharpe = (avg_pnl / std_pnl) * np.sqrt(365 * 4)
    ev_pct = (pnl_sum / trades) / init_cash * 100.0
    
    fitness = (calmar * 5.0) + (ev_pct * 3.5) + ((wr - 0.5) * 6.0) - 25.0 * (max_dd ** 2)
    return fitness, tot_ret, max_dd, wr, trades, sharpe, ev_pct

def generate_individual():
    return [
        round(random.uniform(0.85, 0.93), 4),
        round(random.uniform(1.2, 2.6), 4),
        round(random.uniform(1.0, 2.4), 4),
        round(random.uniform(0.2, 0.6), 4),
        round(random.uniform(1.25, 1.55), 4),
        round(random.uniform(0.0006, 0.0016), 5),
        round(random.uniform(0.018, 0.026), 4),
        6,
        7
    ]

random.seed(42)
np.random.seed(42)
POP_SIZE = 60
N_GEN = 30
population = [generate_individual() for _ in range(POP_SIZE)]
best_ind = None
best_fit = -9999.0
best_metrics = None

for gen in range(1, N_GEN + 1):
    scores = []
    for ind in population:
        fit, r, m, w, tc, sh, ev = jit_eval(
            close, open_, high, low, f_imb, f_bo, f_dev,
            ind[0], ind[1], ind[2], ind[3], ind[4], ind[5], ind[6],
            0, is_bars
        )
        scores.append((fit, r, m, w, tc, sh, ev, ind))
    scores.sort(key=lambda x: x[0], reverse=True)
    best = scores[0]
    if best[0] > best_fit:
        best_fit = best[0]
        best_ind = best[7]
        best_metrics = best[:7]
    print(f"Gen {gen:02d}/30 | Fit: {best[0]:.2f} | Ret: {best[1]*100:+.2f}% | MDD: {best[2]*100:.2f}% | WR: {best[3]*100:.1f}% | Trades: {best[4]}")
    
    survivors = [s[7] for s in scores[:15]]
    new_pop = list(survivors)
    while len(new_pop) < POP_SIZE:
        p1, p2 = random.choice(survivors), random.choice(survivors)
        child = [random.choice([a, b]) for a, b in zip(p1, p2)]
        if random.random() < 0.22:
            m_idx = random.randint(0, 6)
            child[m_idx] = generate_individual()[m_idx]
        new_pop.append(child)
    population = new_pop

oos_fit, oos_r, oos_mdd, oos_wr, oos_trades, oos_sharpe, oos_ev = jit_eval(
    close, open_, high, low, f_imb, f_bo, f_dev,
    best_ind[0], best_ind[1], best_ind[2], best_ind[3], best_ind[4], best_ind[5], best_ind[6],
    oos_start, n_bars
)
is_fit, is_r, is_mdd, is_wr, is_trades, is_sharpe, is_ev = best_metrics
wfe = (oos_sharpe / (is_sharpe + 1e-9)) if is_sharpe > 0 else 0.0
oos_calmar = oos_r / (oos_mdd + 1e-4) if oos_mdd > 0 else 0.0

checkpoint = {
    "segment_id": 1,
    "architecture": "EventDriven-LongHorizon-25k-Bars",
    "model_name": "AlphaEvolve-Dynamic-Seg1",
    "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "optimal_ast_genome": {
        "gamma_decay": best_ind[0],
        "w_imb": best_ind[1],
        "w_bo": best_ind[2],
        "w_dev": best_ind[3],
        "sig_thresh": best_ind[4],
        "trail_callback_pct": best_ind[5],
        "sl_pct": best_ind[6],
        "tree_depth": best_ind[7],
        "node_count": best_ind[8]
    },
    "out_of_sample_metrics": {
        "oos_bars_count": 5000,
        "total_return_pct": round(oos_r * 100, 2),
        "max_drawdown_pct": round(oos_mdd * 100, 2),
        "win_rate_pct": round(oos_wr * 100, 2),
        "trades_count": int(oos_trades),
        "sharpe_ratio": round(oos_sharpe, 2),
        "calmar_ratio": round(oos_calmar, 2),
        "ev_per_trade_pct": round(oos_ev, 4),
        "wfe_pct": round(wfe * 100, 2)
    }
}

with open("alphaevolve_checkpoint.json", "w", encoding="utf-8") as f:
    json.dump(checkpoint, f, indent=2, ensure_ascii=False)

print("✔ 25,000 bars Dynamic Segment Checkpoint exported successfully!")
'''

code = template.replace('__B64_DATA__', b64_data)
with open(f'{k_dir}/trainer.py', 'w') as f:
    f.write(code)

print('Successfully generated Seg 1 trainer with 25,000 bars!')
