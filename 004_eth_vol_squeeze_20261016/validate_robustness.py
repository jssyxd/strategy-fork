"""
validate_robustness.py - 策略 004: ETH 波动率挤压策略 样本内外 WFE 与蒙特卡洛压力测试
"""

import os
import sys
import numpy as np
import pandas as pd

def run_validation(data_path="data_eth_1h_real.parquet"):
    if not os.path.exists(data_path):
        alt_path = "../to-research/009_eth_squeeze/data_eth_1h_real.parquet"
        if os.path.exists(alt_path):
            data_path = alt_path
        else:
            raise FileNotFoundError(f"Cannot find {data_path}")

    df = pd.read_parquet(data_path)
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    n_bars = len(close)

    log_hl = np.log(high / low)
    parkinson_var = (log_hl ** 2) / (4.0 * np.log(2.0))
    rv = np.sqrt(pd.Series(parkinson_var).rolling(24).mean().fillna(0.001).values * 8760)

    bb_mid = pd.Series(close).rolling(20).mean()
    bb_std = pd.Series(close).rolling(20).std()
    bb_upper = bb_mid + 2.0 * bb_std
    bb_lower = bb_mid - 2.0 * bb_std

    atr = pd.Series(np.maximum(high - low, np.abs(high - pd.Series(close).shift(1)))).rolling(20).mean()
    keltner_upper = bb_mid + 1.5 * atr
    keltner_lower = bb_mid - 1.5 * atr

    squeeze_on = (bb_lower > keltner_lower) & (bb_upper < keltner_upper)
    squeeze_fired = (~squeeze_on) & (pd.Series(squeeze_on).shift(1).fillna(False))

    iv = rv + 0.05
    iv_pct = pd.Series(iv).rolling(168).rank(pct=True).fillna(0.5).values

    def run_slice(start_idx, end_idx):
        capital = 30000000.0 / 7.20
        initial_usd = capital
        trades = []
        equity_curve = [capital]
        pos_type = 'NONE'
        entry_idx = 0
        entry_px = 0.0
        peak_move = 0.0
        entry_capital = capital
        alloc = 0.32
        trail_mult = 2.5

        for t in range(start_idx, end_idx):
            s = close[t]
            if pos_type != 'NONE':
                hours = t - entry_idx
                move = abs(s - entry_px) / entry_px
                peak_move = max(peak_move, move)
                must_exit = False
                pnl = 0.0
                if pos_type == 'LONG_STRADDLE':
                    if (peak_move > 0.04 and (peak_move - move) > 0.015) or hours >= 96:
                        must_exit = True
                        payoff = move * trail_mult - 0.030
                        pnl = entry_capital * alloc * payoff
                elif pos_type == 'SHORT_IC':
                    if hours >= 72 or move > 0.045:
                        must_exit = True
                        if move < 0.035:
                            pnl = entry_capital * (alloc * 0.8) * 0.028
                        else:
                            pnl = - entry_capital * (alloc * 0.8) * 0.040
                if must_exit:
                    fee = entry_capital * alloc * 0.0006
                    net_pnl = pnl - fee
                    capital += net_pnl
                    trades.append(net_pnl)
                    pos_type = 'NONE'
                    peak_move = 0.0
            if pos_type == 'NONE':
                if squeeze_fired.iloc[t] and iv_pct[t] < 0.40:
                    pos_type = 'LONG_STRADDLE'
                    entry_idx = t
                    entry_px = s
                    peak_move = 0.0
                    entry_capital = capital
                elif iv_pct[t] > 0.82 and (rv[t] < pd.Series(rv).iloc[t-1]):
                    pos_type = 'SHORT_IC'
                    entry_idx = t
                    entry_px = s
                    peak_move = 0.0
                    entry_capital = capital
            equity_curve.append(capital)
            
        equity_arr = np.array(equity_curve)
        ret = np.diff(equity_arr) / equity_arr[:-1]
        sharpe = (np.mean(ret) / (np.std(ret) + 1e-9)) * np.sqrt(8760 / 24)
        tot_ret = (equity_arr[-1] - initial_usd) / initial_usd
        days = (end_idx - start_idx) / 24.0
        cagr = ((1.0 + tot_ret) ** (365.0 / days) - 1.0) * 100.0
        peak = np.maximum.accumulate(equity_arr)
        max_dd = np.max((peak - equity_arr) / peak) * 100.0
        return sharpe, cagr, max_dd, trades

    print("=" * 65)
    print("WALK-FORWARD & IN-SAMPLE / OUT-OF-SAMPLE TEST (60% IS, 40% OOS)")
    print("=" * 65)
    split = int(n_bars * 0.60)
    s_is, c_is, dd_is, trades_is = run_slice(168, split)
    s_oos, c_oos, dd_oos, trades_oos = run_slice(split, n_bars)
    wfe = s_oos / (s_is + 1e-6)

    print(f"样本内 (IS  0 - {split} Bars)  : Sharpe: {s_is:.2f} | CAGR: {c_is:.2f}% | MaxDD: {dd_is:.2f}%")
    print(f"样本外 (OOS {split} - {n_bars} Bars): Sharpe: {s_oos:.2f} | CAGR: {c_oos:.2f}% | MaxDD: {dd_oos:.2f}%")
    print(f"步进效率 (WFE = OOS / IS) : {wfe:.1%} (合格准入线 >= 60.0%)")
    print(f"判定结果: {'PASSED [Robust]' if wfe >= 0.60 else 'FAILED'}")

    # Monte Carlo 1,000 runs
    print("\n" + "=" * 65)
    print("1,000 次蒙特卡洛交易序列置换压力测试")
    print("=" * 65)
    all_trades = trades_is + trades_oos
    rng = np.random.RandomState(42)
    mc_dds = []
    for _ in range(1000):
        resampled = rng.choice(all_trades, size=len(all_trades), replace=True)
        eq = 30000000.0 + np.cumsum(resampled) * 7.20
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / peak * 100.0
        mc_dds.append(np.max(dd))
        
    p95_dd = np.percentile(mc_dds, 95)
    p99_dd = np.percentile(mc_dds, 99)
    print(f"蒙特卡洛 95% 置信度最大回撤 (VaR 95%): {p95_dd:.2f}%")
    print(f"蒙特卡洛 99% 置信度最大回撤 (VaR 99%): {p99_dd:.2f}%")
    print(f"判定结果: {'PASSED [VaR 95% <= 15.0%]' if p95_dd <= 15.0 else 'FAILED'}")

if __name__ == '__main__':
    run_validation()
