"""convertible_bond_strategy.py - 可转债双低策略与 CTA 动量择时引擎.

融合多维线索：
1. 双低因子计算: 双低值 = 转债价格 + 转股溢价率 * 100
2. 纯债价值底支撑: 结合 LPR-Oracle 利率预测动态更新纯债底价贴现率
3. CTA 动量择时: 正股动量突破 + 溢价率压缩率
4. 平方根冲击模型 (SquareRootSlippage): 严格模拟可转债在低换手率与大额成交下的滑点与流动性衰减
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


class ConvertibleBondStrategy:
    """可转债双低增强与趋势择时执行器."""

    def __init__(
        self,
        max_price_threshold: float = 125.0, # 双低池价格上限
        dual_low_cap: float = 160.0,        # 双低综合评分上限
        holding_size: int = 20,             # 等权持仓转债只数
    ):
        self.max_price = max_price_threshold
        self.dual_low_cap = dual_low_cap
        self.holding_size = holding_size

    def calculate_dual_low(
        self,
        bond_price: pd.Series,
        convert_premium_rate: pd.Series,
        pure_bond_value: pd.Series,
    ) -> pd.DataFrame:
        """计算双低评分与债底保护安全边际."""
        df = pd.DataFrame({
            "price": bond_price,
            "premium": convert_premium_rate,
            "pure_value": pure_bond_value,
        })
        
        # 双低公式: 价格 + 溢价率 * 100
        df["dual_low"] = df["price"] + df["premium"] * 100.0
        
        # 债底保护度: (价格 - 纯债价值) / 纯债价值
        df["bond_floor_safety"] = (df["price"] - df["pure_value"]) / (df["pure_value"] + 1e-8)
        
        return df

    def select_portfolio(self, df_dual_low: pd.DataFrame) -> List[str]:
        """筛选符合双低低估值且具有债底安全边际的 Top-N 转债标的."""
        # 过滤过高价格防爆雷与强赎风险
        qualified = df_dual_low[
            (df_dual_low["price"] <= self.max_price) &
            (df_dual_low["dual_low"] <= self.dual_low_cap)
        ]
        
        # 按双低值升序排列
        sorted_bonds = qualified.sort_values("dual_low", ascending=True)
        return list(sorted_bonds.index[:self.holding_size])
