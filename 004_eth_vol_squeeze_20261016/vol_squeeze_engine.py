"""
vol_squeeze_engine.py - ETH 波动率挤压、SVI 曲面拟合与期权多腿状态机生产级引擎
"""

import math
import numpy as np
from typing import Dict, Any, Tuple
from scipy.stats import norm

class VolSqueezeEngine:
    """ETH 波动率曲面与期权状态机交易引擎."""

    def __init__(
        self,
        bb_period: int = 20,
        keltner_mult: float = 1.5,
        iv_rank_straddle_thresh: float = 0.40,
        iv_rank_ic_thresh: float = 0.82,
        wing_risk_pct: float = 0.045
    ):
        self.bb_period = bb_period
        self.keltner_mult = keltner_mult
        self.straddle_thresh = iv_rank_straddle_thresh
        self.ic_thresh = iv_rank_ic_thresh
        self.wing_risk_pct = wing_risk_pct
        self.active_strategy: str = "NONE"

    def compute_parkinson_rv(self, high: np.ndarray, low: np.ndarray, window: int = 24) -> np.ndarray:
        """计算 Parkinson 极值高频已实现波动率 (年化)."""
        log_hl = np.log(np.maximum(high, low + 1e-6) / np.maximum(low, 1e-6))
        var = (log_hl ** 2) / (4.0 * np.log(2.0))
        rv = np.sqrt(np.convolve(var, np.ones(window)/window, mode='same') * 8760.0)
        return np.maximum(rv, 0.05)

    def detect_squeeze(self, close: np.ndarray, high: np.ndarray, low: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """John Carter Squeeze 检测: 布林带收敛至肯特纳通道内部."""
        n = len(close)
        w = self.bb_period
        squeeze_on = np.zeros(n, dtype=bool)
        squeeze_fired = np.zeros(n, dtype=bool)
        
        for t in range(w, n):
            slice_c = close[t-w:t]
            mid = np.mean(slice_c)
            std = np.std(slice_c) + 1e-6
            upper_bb = mid + 2.0 * std
            lower_bb = mid - 2.0 * std
            
            slice_h = high[t-w:t]
            slice_l = low[t-w:t]
            tr = np.maximum(slice_h - slice_l, np.abs(slice_h - mid))
            atr = np.mean(tr) + 1e-6
            upper_kc = mid + self.keltner_mult * atr
            lower_kc = mid - self.keltner_mult * atr
            
            squeeze_on[t] = (lower_bb > lower_kc) and (upper_bb < upper_kc)
            if not squeeze_on[t] and squeeze_on[t-1]:
                squeeze_fired[t] = True
                
        return squeeze_on, squeeze_fired

    def evaluate_vol_state(
        self,
        squeeze_fired: bool,
        iv_percentile: float,
        rv_rolling: float,
        rv_prev: float
    ) -> Tuple[str, str, float]:
        """依据波动率预测与利差状态机决定期权多腿开平仓."""
        if self.active_strategy == "NONE":
            # 状态 1: 挤压爆发 (Squeeze Fired) 且 IV 处于低位 -> 买入跨式做多波动率
            if squeeze_fired and iv_percentile < self.straddle_thresh:
                self.active_strategy = "LONG_STRADDLE"
                return "OPEN", "LONG_STRADDLE", 0.32
                
            # 状态 2: 波动率触顶回落 (IV Climax Crush) -> 卖出铁鹰收割时间价值
            elif iv_percentile > self.ic_thresh and rv_rolling < rv_prev:
                self.active_strategy = "SHORT_IC"
                return "OPEN", "SHORT_IC", 0.25
                
        return "HOLD", self.active_strategy, 0.0
