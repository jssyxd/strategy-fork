# -*- coding: utf-8 -*-
import os, glob, json, pandas as pd, numpy as np

BASE_DIR = '/home/da/.omp/wt/dynamic/012_event_driven_dynamic_training'

all_trades = []
seg_summary = []

for k in range(1, 16):
    f_tr = f'{BASE_DIR}/trades/nautilus_trades_seg_{k}.csv'
    f_ckpt = f'{BASE_DIR}/checkpoints/alphaevolve_checkpoint_seg_{k}.json'
    
    if os.path.exists(f_tr) and os.path.exists(f_ckpt):
        df_tr = pd.read_csv(f_tr)
        with open(f_ckpt) as fc:
            ckpt = json.load(fc)
            
        all_trades.append(df_tr)
        
        tc = len(df_tr)
        wins = len(df_tr[df_tr['net_pnl'] > 0])
        wr = (wins / tc * 100.0) if tc > 0 else 0.0
        tot_pnl = df_tr['net_pnl'].sum()
        ret_pct = (tot_pnl / 10000.0) * 100.0
        
        # Parse trigger info from reports or log
        start_t = df_tr['entry_time'].iloc[0] if tc > 0 else "N/A"
        end_t = df_tr['exit_time'].iloc[-1] if tc > 0 else "N/A"
        
        seg_summary.append({
            'seg_id': k,
            'model_name': ckpt['model_name'],
            'start_time': start_t,
            'end_time': end_t,
            'trades': tc,
            'wins': wins,
            'losses': tc - wins,
            'win_rate_pct': round(wr, 2),
            'net_pnl_usd': round(tot_pnl, 2),
            'ret_pct': round(ret_pct, 2)
        })

df_summary = pd.DataFrame(seg_summary)
print('=== 15 EVENT-DRIVEN DYNAMIC RETRAINING SEGMENTS SUMMARY ===')
print(df_summary.to_string(index=False))

# Full 2-year portfolio metrics
df_all = pd.concat(all_trades, ignore_index=True)
df_all['trade_id'] = range(1, len(df_all) + 1)
df_all.to_csv(f'{BASE_DIR}/trades/all_event_driven_trades_2024_2026.csv', index=False)

capital = 10000.0
eq = [capital]
for p in df_all['net_pnl']:
    capital += p
    eq.append(capital)
eq = np.array(eq)
peak = np.maximum.accumulate(eq)
mdd = float(np.max((peak - eq) / peak * 100.0))
tot_ret = (capital - 10000.0) / 10000.0 * 100.0
tot_t = len(df_all)
tot_w = len(df_all[df_all['net_pnl'] > 0])
tot_wr = (tot_w / tot_t * 100.0) if tot_t else 0.0
sharpe = float(df_all['net_pnl'].mean() / (df_all['net_pnl'].std() + 1e-9) * np.sqrt(365 * 4))
wins_sum = df_all[df_all['net_pnl'] > 0]['net_pnl'].sum()
losses_sum = abs(df_all[df_all['net_pnl'] <= 0]['net_pnl'].sum())
pf = wins_sum / losses_sum if losses_sum else 999.0
calmar = tot_ret / mdd if mdd > 0 else 0.0

print('\n=== TOTAL PORTFOLIO OVER 2 YEARS (EVENT-DRIVEN DYNAMIC RETRAINING) ===')
print(f'Total Trades: {tot_t}')
print(f'Total Win Trades: {tot_w} ({tot_wr:.2f}%)')
print(f'Total Net Profit: ${capital - 10000.0:.2f} (Total Return: +{tot_ret:.2f}%)')
print(f'Max Drawdown across 2 years: {mdd:.2f}%')
print(f'Sharpe Ratio: {sharpe:.2f}')
print(f'Profit Factor: {pf:.2f}')
print(f'Calmar Ratio: {calmar:.2f}')
