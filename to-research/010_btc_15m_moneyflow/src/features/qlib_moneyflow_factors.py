"""
Worker 2A: AlphaGPT & Qlib Micro-Liquidity Factor Engineering.
Extracts:
1. ofi_impulse: Order Flow Imbalance volume-weighted price displacement.
2. cmf_16: Chaikin Money Flow across 16 bars (4h window).
3. fvg_net: Fair Value Gap net absorption normalized by ATR.
4. sweep_intensity: Liquidity sweep above swing highs / below swing lows.
5. ema_ratio & ema_accel: Dual EMA momentum & acceleration.
6. vol_compression: High-Low range relative to ATR (regime detection).
7. alpha_composite: Stack-VM composite score combining moneyflow & momentum.
"""

from pathlib import Path
import numpy as np
import pandas as pd

def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()

def compute_all_factors(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    open_ = df['open']
    high = df['high']
    low = df['low']
    close = df['close']
    volume = df['volume']
    
    atr = compute_atr(high, low, close, period=14)
    features['atr14'] = atr
    
    # 1. OFI (Order Flow Imbalance Proxy)
    hl_range = (high - low).replace(0, 1e-6)
    cl_v = ((2.0 * close - high - low) / hl_range) * volume
    features['ofi_impulse'] = cl_v.rolling(window=8).mean() / (volume.rolling(window=8).mean() + 1e-6)
    
    # 2. CMF (Chaikin Money Flow) 16 bars
    features['cmf_16'] = cl_v.rolling(16).sum() / (volume.rolling(16).sum() + 1e-6)
    
    # 3. FVG (Fair Value Gap)
    bull_fvg = (low - high.shift(2)).clip(lower=0)
    bear_fvg = (low.shift(2) - high).clip(lower=0)
    features['fvg_net'] = (bull_fvg - bear_fvg) / (atr + 1e-6)
    
    # 4. Sweep Intensity (16-bar swings)
    swing_high = high.rolling(window=16).max().shift(1)
    swing_low = low.rolling(window=16).min().shift(1)
    sweep_up = (high - swing_high).clip(lower=0) / (atr + 1e-6)
    sweep_down = (swing_low - low).clip(lower=0) / (atr + 1e-6)
    features['sweep_intensity'] = sweep_up - sweep_down
    
    # 5. Dual EMA Momentum & Acceleration
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    features['ema_ratio'] = (ema9 - ema21) / (atr + 1e-6)
    features['ema_accel'] = features['ema_ratio'].diff(3)
    
    # 6. Volatility Compression
    vol_ratio = (high - low) / (atr + 1e-6)
    features['vol_compression'] = vol_ratio.rolling(8).mean()
    
    # 7. AlphaGPT Stack VM Composite Signal
    # Multi-factor linear/non-linear blend
    # z-score normalization
    z_ofi = (features['ofi_impulse'] - features['ofi_impulse'].rolling(96).mean()) / (features['ofi_impulse'].rolling(96).std() + 1e-6)
    z_cmf = (features['cmf_16'] - features['cmf_16'].rolling(96).mean()) / (features['cmf_16'].rolling(96).std() + 1e-6)
    z_fvg = features['fvg_net']
    z_mom = features['ema_ratio']
    
    features['alpha_composite'] = (0.35 * z_ofi + 0.25 * z_cmf + 0.20 * z_fvg + 0.20 * z_mom).clip(-3.0, 3.0)
    
    # Forward Returns for audit (1 bar = 15m, 4 bars = 1h)
    features['fwd_ret_1'] = close.pct_change(1).shift(-1)
    features['fwd_ret_4'] = close.pct_change(4).shift(-4)
    
    return features
