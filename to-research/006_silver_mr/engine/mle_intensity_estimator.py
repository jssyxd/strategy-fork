"""mle_intensity_estimator.py - 极大似然估计 (MLE) 动态订单到达强度 kappa 与波动率估计

根据 Avellaneda-Stoikov 微观结构理论:
主动吃单到达强度 Lambda(delta) = A * exp(-kappa * delta)
其中 delta 为挂单距离盘口中间价的价差。
本模块在滑动窗口内对订单簿快照与主动成交事件执行在线 MLE 标定，
实时输出当前市场的流动性吸收效率 kappa(t) 与局部微观波动率 sigma(t)。
"""

import numpy as np
from typing import List, Dict, Tuple


class MLEIntensityEstimator:
    """动态微观流动性参数在线估计器"""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.price_history: List[float] = []
        self.spread_events: List[float] = []

    def update_tick(self, mid_price: float, filled_spread: float) -> Tuple[float, float]:
        """
        接收每次成交事件并更新当前估计值:
        - filled_spread: 本次成交时挂单距离中枢的偏离距离
        返回: (kappa_t, sigma_t)
        """
        self.price_history.append(mid_price)
        if filled_spread > 0:
            self.spread_events.append(filled_spread)

        if len(self.price_history) > self.window_size:
            self.price_history.pop(0)
        if len(self.spread_events) > self.window_size:
            self.spread_events.pop(0)

        # 1. 局部对数收益率波动率 sigma 估计
        if len(self.price_history) >= 10:
            prices = np.array(self.price_history)
            rets = np.diff(np.log(prices))
            sigma_t = float(np.std(rets))
        else:
            sigma_t = 0.001

        # 2. 极大似然估计 kappa:
        # 在指数分布或 Poisson 到达假设下，MLE 估计量 kappa = 1 / mean(delta)
        if len(self.spread_events) >= 5:
            mean_delta = np.mean(self.spread_events)
            kappa_t = float(1.0 / mean_delta) if mean_delta > 1e-4 else 1.5
        else:
            kappa_t = 1.5

        # 限制合理数值边界
        kappa_t = float(np.clip(kappa_t, 0.2, 5.0))
        return kappa_t, sigma_t
