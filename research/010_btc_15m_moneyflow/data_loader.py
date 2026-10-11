"""
Data Loader for BTC 15M MoneyFlow Strategy Research
=====================================
Purpose: Load & validate multi-asset OHLCV Parquet data from JasonleeQAQ/multi-asset-ohlcv
Workflow: Phase 0 (Data Preparation) → Phase 1 (Hypothesis & Topology)

Author: AI Agent (pi) - Herdr Swarm
Date: 2026-10-11
"""

import pandas as pd
import polars as pl
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('research/010_btc_15m_moneyflow/logs/data_loader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DATA_ROOT = Path("../../data/multi-asset-ohlcv")  # Adjust to your clone path
OUTPUT_DIR = Path("data_processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Symbol mapping: (asset_class, folder_prefix, timeframe)
SYMBOLS_CONFIG = {
    # Crypto USDT Perpetuals
    "BTCUSDT": ("crypto", "coinraw_data/BTCUSDTraw_data", "15m"),
    "ETHUSDT": ("crypto", "coinraw_data/ETHUSDTraw_data", "15m"),
    "SOLUSDT": ("crypto", "coinraw_data/SOLUSDTraw_data", "15m"),
    
    # FX & Commodities
    "XAUUSD": ("commodity", "xauusdraw_data", "15m"),
    "USOUSD": ("commodity", "usousdraw_data", "15m"),
    "EURUSD": ("fx", "eurusdraw_data", "15m"),
    "GBPUSD": ("fx", "gbpusdraw_data", "15m"),
}

# Time ranges for backtest
IS_START = "2023-01-01"  # Sample In (Training)
IS_END = "2024-12-31"
OOS_START = "2025-01-01"  # Sample Out (Test)
OOS_END = "2026-02-28"

class DataLoader:
    """Load & process OHLCV Parquet data for backtesting"""
    
    def __init__(self, data_root: Path = DATA_ROOT):
        self.data_root = Path(data_root)
        if not self.data_root.exists():
            raise FileNotFoundError(
                f"Data root not found: {self.data_root}\n"
                f"Please clone: git clone https://github.com/JasonleeQAQ/multi-asset-ohlcv.git"
            )
        logger.info(f"DataLoader initialized with root: {self.data_root}")
    
    def get_file_path(self, symbol: str, timeframe: str, year_month: str) -> Path:
        """Construct parquet file path for a symbol, timeframe, and month."""
        asset_class, folder, _ = SYMBOLS_CONFIG.get(symbol, (None, None, None))
        
        if asset_class == "crypto":
            return self.data_root / folder / "ohlcv" / timeframe / f"{symbol}_{timeframe}_ohlcv_{year_month}.parquet"
        else:
            # FX & commodity naming: lowercase symbol
            symbol_lower = symbol.lower()
            return self.data_root / folder / "ohlcv" / timeframe / f"{symbol_lower}_{timeframe}_ohlcv_{year_month}.parquet"
    
    def load_symbol_range(
        self, 
        symbol: str, 
        start_date: str = IS_START, 
        end_date: str = OOS_END, 
        timeframe: str = "15m"
    ) -> pd.DataFrame:
        """
        Load OHLCV data for a symbol across a date range.
        
        Args:
            symbol: e.g. "BTCUSDT", "XAUUSD"
            start_date: "YYYY-MM-DD"
            end_date: "YYYY-MM-DD"
            timeframe: "15m", "1h", etc.
        
        Returns:
            DataFrame with DatetimeIndex, columns [open, high, low, close, volume]
        """
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        
        months = pd.date_range(start=start.to_period('M').start_time, 
                               end=end.to_period('M').end_time, 
                               freq='MS')
        
        frames = []
        for month in months:
            year_month = month.strftime('%Y-%m')
            filepath = self.get_file_path(symbol, timeframe, year_month)
            
            if not filepath.exists():
                logger.warning(f"File not found: {filepath}")
                continue
            
            try:
                df = pd.read_parquet(filepath)
                # Filter to date range
                df = df[(df.index >= start) & (df.index <= end)]
                frames.append(df)
                logger.info(f"Loaded {year_month}: {len(df)} bars from {filepath.name}")
            except Exception as e:
                logger.error(f"Error loading {filepath}: {e}")
                continue
        
        if not frames:
            raise ValueError(f"No data loaded for {symbol} in range {start_date} ~ {end_date}")
        
        result = pd.concat(frames, axis=0).sort_index()
        logger.info(f"✅ {symbol}: {len(result)} total bars ({result.index[0]} ~ {result.index[-1]})")
        return result
    
    def load_multiple_symbols(
        self, 
        symbols: List[str], 
        start_date: str = IS_START, 
        end_date: str = OOS_END
    ) -> Dict[str, pd.DataFrame]:
        """Load multiple symbols and return as dict."""
        result = {}
        for symbol in symbols:
            try:
                result[symbol] = self.load_symbol_range(symbol, start_date, end_date)
            except Exception as e:
                logger.error(f"Failed to load {symbol}: {e}")
        
        return result
    
    def validate_data(self, df: pd.DataFrame, symbol: str) -> Tuple[bool, List[str]]:
        """
        Validate OHLCV data integrity.
        
        Returns: (is_valid, list_of_issues)
        """
        issues = []
        
        # Check required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            issues.append(f"Missing columns: {missing}")
        
        # Check for gaps (for crypto 24/7, minimal gaps expected)
        if len(df) > 1:
            expected_freq = pd.Timedelta(minutes=15)
            gaps = df.index.to_series().diff() > expected_freq * 2
            if gaps.sum() > 0:
                logger.warning(f"{symbol}: {gaps.sum()} detected time gaps (expected for FX/commodities during non-trading hours)")
        
        # Check for NaN
        nan_count = df.isna().sum().sum()
        if nan_count > 0:
            issues.append(f"Found {nan_count} NaN values")
        
        # Check price logic
        bad_logic = (df['high'] < df['low']) | (df['close'] > df['high']) | (df['close'] < df['low'])
        if bad_logic.sum() > 0:
            issues.append(f"Price logic violated in {bad_logic.sum()} rows")
        
        # Check volume
        if (df['volume'] < 0).any():
            issues.append("Negative volume detected")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def export_for_backtest(
        self, 
        df: pd.DataFrame, 
        symbol: str, 
        sample_type: str = "IS"  # "IS" or "OOS"
    ) -> Path:
        """Export validated data to backtest-ready Parquet."""
        # Add technical columns for factor computation
        df_processed = df.copy()
        df_processed['returns'] = df_processed['close'].pct_change()
        df_processed['log_returns'] = np.log(df_processed['close'] / df_processed['close'].shift(1))
        
        # Simple VWAP
        df_processed['vwap'] = (df_processed['volume'] * (df_processed['high'] + df_processed['low']) / 2).rolling(20).sum() / \
                               df_processed['volume'].rolling(20).sum()
        
        output_path = OUTPUT_DIR / f"{symbol}_{sample_type}_{pd.Timestamp.now().strftime('%Y%m%d')}.parquet"
        df_processed.to_parquet(output_path, compression='snappy', index=True)
        logger.info(f"✅ Exported {symbol} ({sample_type}) to {output_path}")
        
        return output_path
    
    def summary_report(self, symbols: List[str]):
        """Generate data availability summary."""
        print("\n" + "="*80)
        print("📊 DATA AVAILABILITY SUMMARY (BTC 15M MoneyFlow Research)")
        print("="*80)
        
        for symbol in symbols:
            try:
                df = self.load_symbol_range(symbol, IS_START, OOS_END)
                is_valid, issues = self.validate_data(df, symbol)
                
                print(f"\n{symbol:12} │ Total Bars: {len(df):8} │ First: {df.index[0].date()} │ Last: {df.index[-1].date()}")
                print(f"{'':12} │ Validity: {'✅ PASS' if is_valid else '❌ FAIL'}")
                
                if not is_valid:
                    for issue in issues:
                        print(f"{'':12} │ ⚠️  {issue}")
                
                # Split summary
                is_start, is_end = pd.Timestamp(IS_START), pd.Timestamp(IS_END)
                oos_start, oos_end = pd.Timestamp(OOS_START), pd.Timestamp(OOS_END)
                
                is_data = df[(df.index >= is_start) & (df.index <= is_end)]
                oos_data = df[(df.index >= oos_start) & (df.index <= oos_end)]
                
                print(f"{'':12} │ Sample-In (2023-2024):  {len(is_data):8} bars")
                print(f"{'':12} │ Sample-Out (2025-2026): {len(oos_data):8} bars")
                
            except Exception as e:
                print(f"\n{symbol:12} │ ❌ ERROR: {str(e)[:60]}")
        
        print("\n" + "="*80 + "\n")


def main():
    """Entry point for Phase 0 data preparation."""
    loader = DataLoader(DATA_ROOT)
    
    # Test data availability for core assets
    test_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSD", "USOUSD"]
    
    logger.info("="*80)
    logger.info("Phase 0: Data Preparation & Validation")
    logger.info("="*80)
    
    # Summary report
    loader.summary_report(test_symbols)
    
    # Load & export BTC for Phase 1 initialization
    logger.info("\nLoading BTC USDT (Core Asset) for Phase 1 initialization...")
    btc_is = loader.load_symbol_range("BTCUSDT", IS_START, IS_END)
    btc_oos = loader.load_symbol_range("BTCUSDT", OOS_START, OOS_END)
    
    # Validate
    is_valid_is, issues_is = loader.validate_data(btc_is, "BTCUSDT (IS)")
    is_valid_oos, issues_oos = loader.validate_data(btc_oos, "BTCUSDT (OOS)")
    
    if is_valid_is and is_valid_oos:
        # Export
        path_is = loader.export_for_backtest(btc_is, "BTCUSDT", "IS")
        path_oos = loader.export_for_backtest(btc_oos, "BTCUSDT", "OOS")
        
        logger.info(f"\n✅ PHASE 0 COMPLETE")
        logger.info(f"Ready for Phase 1: Factor Mining & Feature Engineering")
        logger.info(f"→ IS data: {path_is}")
        logger.info(f"→ OOS data: {path_oos}")
    else:
        logger.error(f"❌ DATA VALIDATION FAILED")
        logger.error(f"Issues (IS): {issues_is}")
        logger.error(f"Issues (OOS): {issues_oos}")


if __name__ == "__main__":
    main()
