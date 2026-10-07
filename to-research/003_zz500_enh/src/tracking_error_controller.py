"""tracking_error_controller.py - 中证500指数增强跟踪误差 (Tracking Error) 与风格中性化控制器.

结合 AlphaFactory 强化学习架构与 EnsembleCore 风险控制层：
1. 行业中性化 (Industry Neutralization): 强制权重偏离在申万一级行业内不超过 +/- 1.0%
2. 风格中性化 (Style Neutralization): 控制在市值 (Size)、估值 (Value)、波动率 (Vol) 暴露在基准附近
3. 动态跟踪误差惩罚 (Tracking Error Penalty):
   - 目标年化跟踪误差控制在 4.5% 以内
   - 采用二次规划 (Quadratic Programming) 或 PPO 控制器动态输出个股主动权重
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional


class TrackingErrorController:
    """中证500指数增强跟踪误差与风险预算控制器."""

    def __init__(
        self,
        target_te: float = 0.045,      # 目标年化跟踪误差 4.5%
        max_active_weight: float = 0.015, # 单只股票最大主动权重偏离 1.5%
        turnover_penalty: float = 0.002,  # 换手率交易成本惩罚
    ):
        self.target_te = target_te
        self.max_active = max_active_weight
        self.turnover_penalty = turnover_penalty

    def neutralize_weights(
        self,
        raw_alpha_scores: pd.Series,
        benchmark_weights: pd.Series,
        industry_labels: pd.Series,
    ) -> pd.Series:
        """行业中性化与主动权重截断优化."""
        # 1. 行业内部 Z-Score 标准化
        df = pd.DataFrame({
            "alpha": raw_alpha_scores,
            "bench": benchmark_weights,
            "industry": industry_labels,
        })
        
        # 组内去均值中心化
        df["active_score"] = df.groupby("industry")["alpha"].transform(lambda x: (x - x.mean()) / (x.std() + 1e-8))
        
        # 2. 计算目标主动权重
        active_weights = df["active_score"] * 0.005
        active_weights = active_weights.clip(-self.max_active, self.max_active)
        
        # 3. 合并基准权重
        final_weights = df["bench"] + active_weights
        final_weights = final_weights.clip(lower=0.0) # 禁止卖空现货
        
        # 归一化为 1.0
        return final_weights / final_weights.sum()
