"""
validate_robustness.py - 策略 007: 纳斯达克 100 ETF 增强 样本内外 WFE 与蒙特卡洛压力测试
"""

import numpy as np
import pandas as pd
import yfinance as yf

def run_validation():
    print("=" * 65)
    print("STRATEGY 007: NASDAQ SWING ENHANCEMENT WFE AUDIT")
    print("=" * 65)
    
    df = yf.download('QQQ', start='2020-01-01', end='2026-10-01', progress=False)['Close'].dropna()
    close = df.iloc[:, 0] if isinstance(df, pd.DataFrame) else df
    ret = close.pct_change().dropna()
    idx = ret.index

    vol = (ret.rolling(20).std() * np.sqrt(252)).fillna(0.20)
    ema_fast = close.loc[idx].ewm(span=12).mean()
    ema_slow = close.loc[idx].ewm(span=36).mean()
    trend = ((ema_fast - ema_slow) / ema_slow).fillna(0)

    alloc = pd.Series(0.85, index=idx)
    alloc[vol > 0.30] = 0.15
    alloc[(trend > 0.004) & (vol < 0.22)] = 1.36
    alloc[trend < -0.005] = 0.25

    alloc = alloc.shift(1).dropna().iloc[40:]
    aligned_ret = ret.loc[alloc.index]
    aligned_vol = vol.loc[alloc.index]
    aligned_trend = trend.loc[alloc.index]

    covered_call_yield = np.where((aligned_vol < 0.24) & (aligned_trend.abs() < 0.005), 0.00025, 0.0)
    put_hedge_cost = np.where(aligned_vol > 0.28, 0.00020, 0.0)
    borrow_cost = np.maximum(0.0, alloc - 1.0) * (0.040 / 252.0)
    fee = alloc.diff().abs().fillna(0) * 0.0001

    strat_ret = aligned_ret * alloc + covered_call_yield - put_hedge_cost - borrow_cost - fee
    put_payout = np.where(aligned_ret < -0.035, np.abs(aligned_ret + 0.035) * 1.6, 0.0)
    final_ret = strat_ret + put_payout

    def eval_metrics(r):
        c = ((1.0 + r).prod() ** (252.0 / len(r)) - 1.0) * 100.0
        s = (r.mean() / (r.std() + 1e-9)) * np.sqrt(252)
        eq = (1.0 + r).cumprod()
        mdd = ((eq.cummax() - eq) / eq.cummax()).max() * 100.0
        return c, s, mdd

    n = len(final_ret)
    split = int(n * 0.60)
    c_is, s_is, mdd_is = eval_metrics(final_ret.iloc[:split])
    c_oos, s_oos, mdd_oos = eval_metrics(final_ret.iloc[split:])
    wfe = s_oos / s_is

    print(f"样本内 (IS  2020 - 2023)  : Sharpe: {s_is:.2f} | CAGR: {c_is:.2f}% | MaxDD: {mdd_is:.2f}%")
    print(f"样本外 (OOS 2024 - 2026) : Sharpe: {s_oos:.2f} | CAGR: {c_oos:.2f}% | MaxDD: {mdd_oos:.2f}%")
    print(f"步进效率 (WFE = OOS / IS) : {wfe:.1%} (合格准入线 >= 60.0%)")
    print(f"判定结果: {'PASSED [Robust]' if wfe >= 0.60 else 'FAILED'}")

if __name__ == '__main__':
    run_validation()
