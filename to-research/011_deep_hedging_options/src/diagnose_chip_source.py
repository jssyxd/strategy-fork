"""diagnose_chip_source.py - Diagnostic tools for A-share chip distribution sources.

Extracted from video screen recordings (t=3:30-3:56).
"""
import numpy as np
import pandas as pd


def diagnose(chip_df: pd.DataFrame) -> dict:
    if chip_df.empty:
        return {"status": "empty"}

    winner_rate_valid = np.all(np.isfinite(chip_df.get("winner_rate", [])))
    weight_avg_valid = np.all(np.isfinite(chip_df.get("weight_avg", [])))

    return {
        "status": "ok" if (winner_rate_valid and weight_avg_valid) else "invalid_values",
        "rows": len(chip_df),
        "winner_rate_valid": bool(winner_rate_valid),
        "weight_avg_valid": bool(weight_avg_valid),
    }
