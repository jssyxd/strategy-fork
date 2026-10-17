"""
Data Adapter for Nautilus Trader Backtest.
Loads multi-source DOGE data from W:\database and converts into native Nautilus Bar objects.
"""

import os
import glob
import pandas as pd
import numpy as np
from nautilus_trader.model import Bar, BarType, Price, Quantity

def load_doge_databank_5m(
    databank_dir="/database/03_governed_lake/nautilus_databank/catalog/data/bar/DOGEUSD.CRYPTO-1-MINUTE-LAST-EXTERNAL",
    years=["2023", "2024", "2025"],
    bar_type_str="DOGEUSD.CRYPTO-5-MINUTE-LAST-EXTERNAL"
):
    """
    Loads 1-minute bars from W:\database\03_governed_lake\nautilus_databank,
    resamples them to 5-minute bars, and converts into Nautilus Bar objects.
    """
    parquet_files = []
    for y in years:
        p = os.path.join(databank_dir, f"{y}.parquet")
        if os.path.exists(p):
            parquet_files.append(p)
            
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found in {databank_dir} for years {years}")

    print(f"Loading {len(parquet_files)} years of governed Databank 1m bars from: {parquet_files}")
    dfs = [pd.read_parquet(f) for f in parquet_files]
    df = pd.concat(dfs, ignore_index=True)
    df = df.set_index("timestamp")
    
    # Resample to 5-minute
    df_5m = df.resample("5min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()
    
    print(f"Resampled {len(df)} 1m bars into {len(df_5m)} 5m bars. Range: {df_5m.index.min()} to {df_5m.index.max()}")
    
    bar_type = BarType.from_str(bar_type_str)
    
    opens = df_5m["open"].values
    highs = df_5m["high"].values
    lows = df_5m["low"].values
    closes = df_5m["close"].values
    volumes = df_5m["volume"].values
    ts_events = df_5m.index.astype("int64").values # nanoseconds UTC
    
    bars = [
        Bar(
            bar_type=bar_type,
            open=Price(float(opens[i]), 5),
            high=Price(float(highs[i]), 5),
            low=Price(float(lows[i]), 5),
            close=Price(float(closes[i]), 5),
            volume=Quantity(float(volumes[i]), 1),
            ts_event=int(ts_events[i]),
            ts_init=int(ts_events[i]),
        )
        for i in range(len(df_5m))
    ]
    return bars, df_5m

def resolve_doge_parquet_path(custom_path=None):
    candidates = [
        custom_path,
        os.path.join(os.path.dirname(__file__), "../data/doge_real_binance_aligned_5m.parquet"),
        os.path.join(os.path.dirname(__file__), "../../to-research/008_doge_momentum/data/doge_real_binance_aligned_5m.parquet"),
        "/workspace/008_doge_momentum/data/doge_real_binance_aligned_5m.parquet",
        "/workspace/003_doge_micro_momentum_carry/data/doge_real_binance_aligned_5m.parquet",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return os.path.abspath(c)
    return custom_path or candidates[1]

def load_doge_real_binance_5m(
    file_path=None,
    bar_type_str="DOGEUSDT.BINANCE-5-MINUTE-LAST-EXTERNAL"
):
    """
    Loads the strategy's dedicated 8,000 real Binance 5m bars with CVD & funding data.
    """
    resolved_path = resolve_doge_parquet_path(file_path)
    if not os.path.exists(resolved_path):
        raise FileNotFoundError(f"File not found: {resolved_path} (checked candidates)")
        
    df = pd.read_parquet(resolved_path)
    bar_type = BarType.from_str(bar_type_str)
    
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    volumes = df["volume"].values
    ts_events = (df["open_time"].values * 1_000_000).astype("int64") # ms to ns
    
    bars = [
        Bar(
            bar_type=bar_type,
            open=Price(float(opens[i]), 5),
            high=Price(float(highs[i]), 5),
            low=Price(float(lows[i]), 5),
            close=Price(float(closes[i]), 5),
            volume=Quantity(float(volumes[i]), 1),
            ts_event=int(ts_events[i]),
            ts_init=int(ts_events[i]),
        )
        for i in range(len(df))
    ]
    return bars, df
