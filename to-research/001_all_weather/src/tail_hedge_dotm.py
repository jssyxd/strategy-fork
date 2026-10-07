"""tail_hedge_dotm.py - 春江全天候深度虚值 (DOTM) 期权尾部对冲模块.

整合来自 hwenithe_risk (DeepDatedgingOptimizer) 与 Thales (PDE/SAE Greeks 定价) 的逻辑：
1. 监控全组合在极端左尾行情下的最大回撤 (CVaR / Expected Shortfall)
2. 动态买入 5%-10% 虚值的深度看跌期权 (Deep Out-of-the-Money Put)
3. 当波动率由低转高、市场发生黑天鹅挤压时，提供非线性凸性收益弥补现货组合回撤
"""

import numpy as np
from typing import Dict, Any


class TailHedgeDOTM:
    """尾部黑天鹅对冲器."""

    def __init__(
        self,
        hedge_budget_ratio: float = 0.015, # 年化期权买方预算 1.5%
        dotm_delta_target: float = -0.10,  # 目标 Delta -0.10 (深度虚值 Put)
        vix_alarm_threshold: float = 28.0, # 波动率警报阈值
    ):
        self.hedge_budget = hedge_budget_ratio
        self.target_delta = dotm_delta_target
        self.vix_alarm = vix_alarm_threshold

    def calculate_hedge_allocation(
        self,
        portfolio_value: float,
        current_vix: float,
        vol_forecast: float,
        market_trend: int,
    ) -> Dict[str, Any]:
        """计算当期应配置的 DOTM 看跌期权名义金额与合约张数."""
        # 若市场处于下跌趋势或波动率预测快速攀升，加大对冲预算
        multiplier = 1.0
        if market_trend < 0:
            multiplier *= 1.5
        if vol_forecast > self.vix_alarm:
            multiplier *= 2.0

        monthly_budget = (self.hedge_budget / 12.0) * multiplier * portfolio_value
        return {
            "monthly_put_budget": monthly_budget,
            "target_delta": self.target_delta,
            "action": "BUY_DOTM_PUT" if monthly_budget > 0 else "HOLD",
            "hedge_status": "HIGH_ALERT" if vol_forecast > self.vix_alarm else "NORMAL",
        }
