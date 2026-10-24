# -*- coding: utf-8 -*-
import os, glob, json, pandas as pd, numpy as np

BASE_DIR = '/home/da/桌面/eth-15-alphaevolve/007_eth_ai_timing_alphaevolve/rolling_walkforward'

folds_data = []
all_trades = []

for k in range(1, 9):
    trade_file = f'{BASE_DIR}/trades/nautilus_trades_fold_{k}.csv'
    if os.path.exists(trade_file):
        df_tr = pd.read_csv(trade_file)
        all_trades.append(df_tr)
        
        tot_trades = len(df_tr)
        wins = len(df_tr[df_tr['net_pnl'] > 0])
        wr = wins / tot_trades * 100 if tot_trades > 0 else 0
        tot_pnl = df_tr['net_pnl'].sum()
        ret_pct = tot_pnl / 10000.0 * 100.0
        
        folds_data.append({
            'fold': k,
            'trades': tot_trades,
            'wins': wins,
            'losses': tot_trades - wins,
            'win_rate_pct': round(wr, 2),
            'net_pnl_usd': round(tot_pnl, 2),
            'ret_pct': round(ret_pct, 2)
        })

df_summary = pd.DataFrame(folds_data)
print('=== 8 FOLDS WALK-FORWARD SUMMARY ===')
print(df_summary.to_string(index=False))

df_all = pd.concat(all_trades, ignore_index=True)
df_all['trade_id'] = range(1, len(df_all) + 1)
df_all.to_csv(f'{BASE_DIR}/trades/all_walkforward_trades_2024_2026.csv', index=False)

# Portfolio simulation over full 2 years with compounding
capital = 10000.0
equity_curve = [capital]
for pnl in df_all['net_pnl']:
    capital += pnl
    equity_curve.append(capital)

eq = np.array(equity_curve)
peak = np.maximum.accumulate(eq)
mdd = float(np.max((peak - eq) / peak * 100.0))
tot_ret = (capital - 10000.0) / 10000.0 * 100.0
tot_t = len(df_all)
tot_w = len(df_all[df_all['net_pnl'] > 0])
tot_wr = tot_w / tot_t * 100.0 if tot_t > 0 else 0.0
sharpe = float(df_all['net_pnl'].mean() / (df_all['net_pnl'].std() + 1e-9) * np.sqrt(365 * 4))

print('\n=== TOTAL PORTFOLIO OVER 2 YEARS (2024-11-01 ~ 2026-10-20) ===')
print(f'Total Trades: {tot_t}')
print(f'Total Win Trades: {tot_w} ({tot_wr:.2f}%)')
print(f'Total Net Profit: ${capital - 10000.0:.2f} (Total Return: +{tot_ret:.2f}%)')
print(f'Max Drawdown across full 2-year rolling period: {mdd:.2f}%')
print(f'Sharpe Ratio: {sharpe:.2f}')
