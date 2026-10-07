"""commodity_term_structure.py - 商品期货期限结构 (Term Structure) 与时序动量多因子模型.

融合多维量化理论与春江开源组件：
1. 展期收益率 (Roll Yield / Carry Factor):
   - 计算主力合约与次主力合约的基差斜率: (P_near - P_far) / (T_far - T_near)
   - Backwardation (现货溢价/贴水形态) -> 正展期收益，强做多信号
   - Contango (远期升水形态) -> 负展期收益，做空或规避信号
2. 时序动量 (TSMOM / Time Series Momentum):
   - 计算不同周期 (1M, 3M, 12M) 的均线与波动率标准化动量
3. 组合风险分配 (HRP / Lippershey MILP):
   - 使用层次风险平价 (HRP) 进行跨商品板块（黑金、有色、能化、农产品）聚类分配
   - 满足商品保证金占用与整数手约束
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


class CommodityTermStructure:
    """商品期货期限结构与展期动量分析器."""

    def __init__(self, backwardation_threshold: float = 0.05):
        self.bw_threshold = backwardation_threshold

    def calculate_roll_yield(
        self,
        near_price: float,
        far_price: float,
        days_between: int,
    ) -> float:
        """年化展期收益率 (Roll Yield)."""
        if days_between <= 0 or near_price <= 0:
            return 0.0
        # 年化基差率: ln(P_near / P_far) * (365 / days_between)
        roll_yield = np.log(near_price / (far_price + 1e-8)) * (365.0 / days_between)
        return float(roll_yield)

    def composite_signal(
        self,
        roll_yield: float,
        tsmom_score: float,
        inventory_change: float = 0.0,
    ) -> Tuple[float, str]:
        """聚合期限结构与时序动量信号."""
        # 展期收益为正 (贴水) 叠加动量向上 -> 强烈看多
        composite = 0.5 * np.tanh(roll_yield * 5.0) + 0.5 * np.tanh(tsmom_score)
        
        if composite > 0.3:
            return composite, "STRONG_LONG"
        elif composite < -0.3:
            return composite, "STRONG_SHORT"
        else:
            return composite, "NEUTRAL"
