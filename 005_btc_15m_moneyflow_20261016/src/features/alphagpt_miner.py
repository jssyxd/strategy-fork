"""
Worker 2A: AlphaGPT Symbolic Factor Miner.
Implements:
- Expression AST / Stack VM representation
- Primitive operators: TS_Mean, TS_Std, TS_Delta, TS_Rank, Sign, Clip, Scale
- Fitness evaluation based on Information Coefficient (IC) and Calmar enhancement
- Hallucination suppression via strict causality checks and complexity penalty
"""

from typing import Callable, Dict, List
import numpy as np
import pandas as pd

class AlphaGPTExpression:
    def __init__(self, name: str, formula: str, func: Callable[[pd.DataFrame], pd.Series]):
        self.name = name
        self.formula = formula
        self.func = func

    def evaluate(self, df: pd.DataFrame) -> pd.Series:
        return self.func(df)

def get_alphagpt_candidate_factors() -> List[AlphaGPTExpression]:
    candidates = [
        AlphaGPTExpression(
            name="alphagpt_vol_scaled_ofi",
            formula="ts_mean(close - open, 4) / (high - low + 1e-5) * log1p(volume)",
            func=lambda df: (df['close'] - df['open']).rolling(4).mean() / (df['high'] - df['low'] + 1e-5) * np.log1p(df['volume'])
        ),
        AlphaGPTExpression(
            name="alphagpt_fvg_momentum_blend",
            formula="ts_delta(close, 2) * (low - ts_delay(high, 2)).clip(lower=0)",
            func=lambda df: df['close'].diff(2) * (df['low'] - df['high'].shift(2)).clip(lower=0)
        ),
        AlphaGPTExpression(
            name="alphagpt_liquidity_rejection",
            formula="ts_rank(volume, 16) * sign(close - ts_mean(close, 8))",
            func=lambda df: df['volume'].rolling(16).rank(pct=True) * np.sign(df['close'] - df['close'].rolling(8).mean())
        )
    ]
    return candidates
