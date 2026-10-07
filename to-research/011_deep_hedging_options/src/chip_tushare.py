"""chip_tushare.py - Tushare A-share chip data extraction and caching.

Extracted from video screen recordings (t=3:30-3:56).
"""
import os
import json
import pandas as pd
import numpy as np


def get_chip_data(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    cache_file = "chip_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if code in data:
                    return pd.DataFrame(data[code])
        except Exception:
            pass

    # Placeholder for tushare pro api
    # pro.cyq_chips(ts_code=code, start_date=start_date, end_date=end_date)
    cols = ["trade_date", "winner_rate", "weight_avg", "cost_ISB", "cost_BSpeilt"]
    df = pd.DataFrame(columns=cols)
    return df
