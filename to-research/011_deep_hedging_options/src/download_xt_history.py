"""download_xt_history.py - Download historical K-line data from XT.com.

Extracted from video screen recordings (t=3:30, t=3:49).
"""
import requests
import pandas as pd


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def download_history(symbol: str = "BTC_USDT", interval: str = "15m", limit: int = 1000) -> pd.DataFrame:
    url = f"https://sapi.xt.com/v4/public/kline"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json().get("result", [])
        records = []
        for row in data:
            records.append({
                "timestamp": row[0],
                "open": _safe_float(row[1]),
                "high": _safe_float(row[2]),
                "low": _safe_float(row[3]),
                "close": _safe_float(row[4]),
                "volume": _safe_float(row[5]),
            })
        return pd.DataFrame(records)
    except Exception as e:
        print(f"Error downloading XT history: {e}")
        return pd.DataFrame()
