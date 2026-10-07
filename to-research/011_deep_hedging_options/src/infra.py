"""infra.py - Infrastructure utilities and validation functions.

Extracted from video screen recordings (t=3:54, t=3:56).
Code reference: not np.isfinite(winner_rate) or not np.isfinite(weight_avg)
"""
import numpy as np


def is_finite(val) -> bool:
    try:
        return bool(np.isfinite(val))
    except Exception:
        return False


def validate_chip_row(winner_rate: float, weight_avg: float) -> bool:
    return is_finite(winner_rate) and is_finite(weight_avg)
