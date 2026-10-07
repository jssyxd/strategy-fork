"""avellaneda_stoikov_smr.py - 白银均值回归 SMR 与做市商微观盘口最优控制模型.

结合 教学素材视频数学讲解与 capacity_tool L2 盘口离散器：
1. Avellaneda-Stoikov 保留价格 (Reservation Price):
   r(s, q, t) = s - q * gamma * sigma^2 * (T - t)
   - s: 市场当前中间价 (Mid Price)
   - q: 当前持仓库存 (Inventory, 多头为正，空头为负)
   - gamma: 风险厌恶系数
   - sigma: 资产瞬时波动率
2. 动态自适应价差 (Optimal Spread) 与非对称挂单:
   - 随市场波动率动态缩放网格宽度
   - 库存偏多时向下倾斜，压低买入挂单意愿，拉高卖出平仓意愿
3. 微观流动性冲击与容量预估:
   - 结合 Q-Learning 冲击乘数 Oracle，测算单笔挂单被逆向选择 (Adverse Selection) 侵蚀的概率
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict


class AvellanedaStoikovSMR:
    """做市商与高频均值回归受约束最优控制执行器."""

    def __init__(
        self,
        risk_aversion: float = 0.1,    # gamma
        terminal_time: float = 1.0,    # T - t
        kappa: float = 1.5,            # 订单流到达强度参数
        max_inventory: int = 10,       # 允许的最大单向持仓手数
    ):
        self.gamma = risk_aversion
        self.T = terminal_time
        self.kappa = kappa
        self.max_q = max_inventory

    def compute_quotes(
        self,
        mid_price: float,
        inventory: int,
        sigma: float,
        time_left: float = 1.0,
    ) -> Dict[str, float]:
        """计算内部保留价格中枢与最优买卖挂单价格 (Bid / Ask)."""
        # 1. 保留价格 (Reservation Price)
        r = mid_price - inventory * self.gamma * (sigma ** 2) * time_left

        # 2. 最优半价差 (Optimal Half-Spread)
        # s_spread = (2 / gamma) * ln(1 + gamma / kappa)
        half_spread = (1.0 / self.gamma) * np.log(1.0 + self.gamma / self.kappa) * (1.0 + 2.0 * sigma)

        # 3. 计算非对称挂单价格
        optimal_bid = r - half_spread
        optimal_ask = r + half_spread

        # 4. 硬性风控边界: 触发库存极值时，停止逆向开仓
        allow_bid = bool(inventory < self.max_q)
        allow_ask = bool(inventory > -self.max_q)

        return {
            "reservation_price": r,
            "optimal_bid": optimal_bid if allow_bid else 0.0,
            "optimal_ask": optimal_ask if allow_ask else 0.0,
            "half_spread": half_spread,
            "allow_buy": allow_bid,
            "allow_sell": allow_ask,
            "inventory_ratio": inventory / self.max_q,
        }
