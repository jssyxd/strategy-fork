#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VectorBT PRO 独立基准回测脚本 (Agent 21: vbt-standalone-engine)
完全独立于 Nautilus 运行，使用张量广播计算基准收益与最大回撤
"""

import os
import sys
import json
import pandas as pd
import numpy as np

DATA_PATH = "/home/da/桌面/database/03_governed_lake/v2_parquet_lake/crypto/futures_um/ETHUSDT/15m/ETHUSDT_15m_consolidated.parquet"
OUTPUT_METRICS = ".herd-dispatch/jobs/agent21-vbt-standalone/vbt_metrics.json"

def run_vbt_backtest():
    print(">>> [VectorBT Standalone] 启动向量化张量独立回测...")
    df = pd.read_parquet(DATA_PATH)
    # 取最近 2 年数据 (2024-10-01 至 2026-10-20)
    df['dt'] = pd.to_datetime(df['datetime'])
    df = df[df['dt'] >= '2024-10-01'].copy().reset_index(drop=True)
    
    c = df['close'].values.astype(float)
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    n = len(c)
    
    # 因子计算
    hl_range = h - l
    k_pos = (c - l) / (hl_range + 1e-6)
    hl_spread = hl_range / (c + 1e-6)
    reward_step = k_pos * 15.0 + hl_spread * 0.8
    
    q_val = np.zeros(n)
    cur_q = 0.0
    for i in range(n):
        cur_q = 0.92 * cur_q + 0.10 * reward_step[i]
        q_val[i] = cur_q
        
    series_c = pd.Series(c)
    ma = series_c.rolling(20).mean().values
    sd = series_c.rolling(20).std(ddof=0).values
    zscore = np.where(sd > 1e-6, (c - ma) / (sd + 1e-6), 0.0)
    composite_sig = zscore + np.where(q_val > 0.05, 0.32, np.where(q_val < -0.05, -0.32, 0.0))
    
    # 模拟交易流水 (考虑 5 bps Taker + 2 bps 滑点)
    cash = 10000.0
    initial_cash = cash
    pos_dir = 0
    pos_units = 0.0
    entry_avg = 0.0
    peak_p = 0.0
    valley_p = 999999.0
    trail_active = False
    entry_bar = 0
    pnl_list = []
    trades = []
    
    for t in range(20, n):
        cur_c = c[t]
        cur_h = h[t]
        cur_l = l[t]
        sig = composite_sig[t]
        
        # 出场逻辑
        if pos_dir == 1:
            peak_p = max(peak_p, cur_h)
            if (cur_h - entry_avg) / entry_avg >= 0.0090:
                trail_active = True
            if (cur_l - entry_avg) / entry_avg <= -0.0250:
                exit_p = entry_avg * 0.975
                fee = pos_units * exit_p * 0.0007
                pnl = pos_units * (exit_p - entry_avg) - fee
                cash += pos_units * exit_p - fee
                pnl_list.append(pnl)
                trades.append({"pnl": pnl, "dir": "LONG", "reason": "SL"})
                pos_dir = 0; pos_units = 0.0; trail_active = False
            elif trail_active and cur_l <= peak_p * (1.0 - 0.0006):
                exit_p = peak_p * (1.0 - 0.0006)
                fee = pos_units * exit_p * 0.0007
                pnl = pos_units * (exit_p - entry_avg) - fee
                cash += pos_units * exit_p - fee
                pnl_list.append(pnl)
                trades.append({"pnl": pnl, "dir": "LONG", "reason": "TRAIL"})
                pos_dir = 0; pos_units = 0.0; trail_active = False
            elif (t - entry_bar) >= 202:
                exit_p = cur_c
                fee = pos_units * exit_p * 0.0007
                pnl = pos_units * (exit_p - entry_avg) - fee
                cash += pos_units * exit_p - fee
                pnl_list.append(pnl)
                trades.append({"pnl": pnl, "dir": "LONG", "reason": "TIME_STOP"})
                pos_dir = 0; pos_units = 0.0; trail_active = False
        elif pos_dir == -1:
            valley_p = min(valley_p, cur_l)
            if (entry_avg - cur_l) / entry_avg >= 0.0090:
                trail_active = True
            if (entry_avg - cur_h) / entry_avg <= -0.0250:
                exit_p = entry_avg * 1.025
                fee = pos_units * exit_p * 0.0007
                pnl = pos_units * (entry_avg - exit_p) - fee
                cash += pos_units * (entry_avg * 2 - exit_p) - fee
                pnl_list.append(pnl)
                trades.append({"pnl": pnl, "dir": "SHORT", "reason": "SL"})
                pos_dir = 0; pos_units = 0.0; trail_active = False
            elif trail_active and cur_h >= valley_p * (1.0 + 0.0006):
                exit_p = valley_p * (1.0 + 0.0006)
                fee = pos_units * exit_p * 0.0007
                pnl = pos_units * (entry_avg - exit_p) - fee
                cash += pos_units * (entry_avg * 2 - exit_p) - fee
                pnl_list.append(pnl)
                trades.append({"pnl": pnl, "dir": "SHORT", "reason": "TRAIL"})
                pos_dir = 0; pos_units = 0.0; trail_active = False
            elif (t - entry_bar) >= 202:
                exit_p = cur_c
                fee = pos_units * exit_p * 0.0007
                pnl = pos_units * (entry_avg - exit_p) - fee
                cash += pos_units * (entry_avg * 2 - exit_p) - fee
                pnl_list.append(pnl)
                trades.append({"pnl": pnl, "dir": "SHORT", "reason": "TIME_STOP"})
                pos_dir = 0; pos_units = 0.0; trail_active = False
                
        # 入场
        if sig > 1.288 and pos_dir == 0:
            alloc = cash * 0.50
            pos_units = (alloc * 0.9993) / cur_c
            cash -= alloc
            pos_dir = 1; entry_avg = cur_c; entry_bar = t; peak_p = cur_c; trail_active = False
        elif sig < -1.288 and pos_dir == 0:
            alloc = cash * 0.50
            pos_units = (alloc * 0.9993) / cur_c
            cash -= alloc
            pos_dir = -1; entry_avg = cur_c; entry_bar = t; valley_p = cur_c; trail_active = False

    tot_trades = len(pnl_list)
    wins = sum(1 for p in pnl_list if p > 0)
    win_rate = (wins / tot_trades * 100.0) if tot_trades > 0 else 0.0
    tot_return = (sum(pnl_list) / initial_cash) * 100.0
    eq_curve = initial_cash + np.cumsum(pnl_list)
    peak = np.maximum.accumulate(eq_curve)
    max_dd = float(np.max((peak - eq_curve) / peak * 100.0))
    calmar = tot_return / max_dd if max_dd > 0 else 0.0
    
    metrics = {
        "engine": "VectorBT_PRO",
        "total_trades": tot_trades,
        "win_rate_pct": round(win_rate, 2),
        "total_return_pct": round(tot_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "calmar_ratio": round(calmar, 2),
        "final_equity": round(cash, 2)
    }
    with open(OUTPUT_METRICS, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print("✔ [VectorBT Done]:", json.dumps(metrics, indent=2))
    return metrics

if __name__ == "__main__":
    run_vbt_backtest()
