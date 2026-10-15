"""
Unified Multi-Asset 15m OHLCV Data Loader.
Supports: BTC, ETH, SOL, XAU, USO, NQ, ES.
Sources: multi-asset-ohlcv (parquet format).
Provides clean DatetimeIndex, UTC normalization, and train/val/test splits.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd

AVAILABLE_SYMBOLS = ["BTC", "ETH", "SOL", "XAU", "USO", "NQ", "ES"]

def get_data_dir() -> Path:
    # First check relative to strategy folder
    candidates = [
        Path(__file__).resolve().parent.parent.parent / "data",
        Path("data"),
        Path("/home/da/桌面/工作流-备份-americaStocks/data/processed"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path("data")

def load_15m_data(
    symbol: str = "BTC",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    data_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Load stitched 15m OHLCV data for given symbol.
    Returns DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
    indexed by UTC DatetimeIndex.
    """
    symbol = symbol.upper()
    if data_dir is None:
        data_dir = get_data_dir()
        
    p1 = data_dir / f"{symbol}_15m_stitched.parquet"
    p2 = data_dir / symbol / "15m" / f"{symbol}_15m_stitched.parquet"
    
    if p1.exists():
        path = p1
    elif p2.exists():
        path = p2
    else:
        raise FileNotFoundError(f"15m data for {symbol} not found in {data_dir}")
        
    df = pd.read_parquet(path)
    
    # Normalize column names to lowercase
    df.columns = [c.lower() for c in df.columns]
    
    # Ensure DatetimeIndex with UTC
    if not isinstance(df.index, pd.DatetimeIndex):
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.set_index("timestamp")
        else:
            df.index = pd.to_datetime(df.index, utc=True)
    elif df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
        
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="first")]
    
    # Ensure standard required columns
    required = ["open", "high", "low", "close", "volume"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column {col} in {symbol} dataset")
            
    df = df[required].astype(float)
    
    # Date slicing
    if start_date:
        df = df[df.index >= pd.to_datetime(start_date, utc=True)]
    if end_date:
        df = df[df.index <= pd.to_datetime(end_date, utc=True)]
        
    return df

def split_is_oos(
    df: pd.DataFrame,
    is_end: str = "2024-12-31 23:59:59",
    oos_start: str = "2025-01-01 00:00:00",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split into In-Sample (IS: <= 2024) and Out-Of-Sample (OOS: >= 2025)."""
    is_df = df[df.index <= pd.to_datetime(is_end, utc=True)]
    oos_df = df[df.index >= pd.to_datetime(oos_start, utc=True)]
    return is_df, oos_df
