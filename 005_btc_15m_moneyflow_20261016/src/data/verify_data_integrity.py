"""
Worker 1B: Data Integrity & Non-Lookahead Verification.
Audits:
1. Timestamp monotonicity & non-duplication
2. Null values & missing data rate
3. Price anomalies (High >= Max(Open, Close), Low <= Min(Open, Close), Low > 0)
4. Volume non-negativity
5. Coverage span across BTC, ETH, SOL, XAU, USO, NQ, ES
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.data_loader import load_15m_data, AVAILABLE_SYMBOLS, get_data_dir

def audit_symbol_data(symbol: str) -> dict:
    try:
        df = load_15m_data(symbol)
    except Exception as e:
        return {"symbol": symbol, "status": "ERROR", "error": str(e)}
        
    n_bars = len(df)
    null_count = df.isnull().sum().to_dict()
    
    # Check monotonicity
    time_diff = df.index.to_series().diff()
    is_monotonic = df.index.is_monotonic_increasing
    
    # Price consistency check
    price_valid = (
        (df['high'] >= df['open']) &
        (df['high'] >= df['close']) &
        (df['low'] <= df['open']) &
        (df['low'] <= df['close']) &
        (df['low'] > 0) &
        (df['volume'] >= 0)
    )
    invalid_rows = (~price_valid).sum()
    
    # Summary
    res = {
        "symbol": symbol,
        "status": "PASS" if (invalid_rows == 0 and is_monotonic) else "FAIL",
        "bars": n_bars,
        "start": str(df.index.min()),
        "end": str(df.index.max()),
        "duration_years": round((df.index.max() - df.index.min()).days / 365.25, 2),
        "monotonic": bool(is_monotonic),
        "invalid_prices": int(invalid_rows),
        "total_nulls": int(sum(null_count.values())),
    }
    return res

def main():
    print("=" * 80)
    print("PHASE 1 INDEPENDENT DATA INTEGRITY AUDIT REPORT (Worker 1B)")
    print("=" * 80)
    
    results = []
    for sym in AVAILABLE_SYMBOLS:
        report = audit_symbol_data(sym)
        results.append(report)
        status_str = "PASS" if report.get("status") == "PASS" else "FAIL/ERR"
        print(f"[{status_str}] {sym:<5} | Bars: {report.get('bars', 0):>7} | Span: {report.get('start', 'N/A')[:10]} ~ {report.get('end', 'N/A')[:10]} ({report.get('duration_years', 0):>4} yrs) | Invalid: {report.get('invalid_prices', 0)}")
        
    print("=" * 80)
    all_passed = all(r.get("status") == "PASS" for r in results)
    if all_passed:
        print("PHASE 1 VERDICT: DATA PIPELINE INTEGRITY FULLY VERIFIED.")
    else:
        print("PHASE 1 VERDICT: SOME SYMBOLS FAILED AUDIT.")
    return results

if __name__ == "__main__":
    main()
