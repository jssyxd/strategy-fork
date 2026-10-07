"""macro_cycle_engine.py - 全天候宏观周期引擎与动态风险预算倾斜.

融合 教学素材视频讲解（桥水全天候中国本土化实现）与 RateOracle 利率周期预警模型：
1. 增长 (Growth) 与通胀 (Inflation) 四象限宏观指标打分系统：
   - 增长分 (Growth Score): PMI动量、社融脉冲、M1-M2剪刀差、中长期贷款、工业品表现
   - 通胀分 (Inflation Score): CPI-PPI剪刀差、大宗商品价格指数、PPI环比动量
2. 趋势与动量确认 (Trend Filter):
   - MA30 / MA60 双均线交叉确认
   - ADX 趋势强度过滤 (ADX > 25 确认强趋势)
3. 动态风险预算倾斜 (Dynamic Risk Budget Shifting):
   - 基础权重由 ERC (Equal Risk Contribution) 风险平价计算
   - 当宏观打分超过阈值 (如 0.8) 时，对顺周期资产进行风险预算倾斜
   - 引入 Multiplicative Weights Update (MWU) 指数衰减更新
4. 标的资产本土化映射矩阵 (Asset Mapping Matrix):
   - 权益类 ETF: 沪深300 (510300), 中证500 (510500), 创业板 (159915)
   - 债券类 ETF: 30年国债 (511090), 10年国债 (511260), 短债 (511360)
   - 商品类 ETF: 黄金 (518880), 豆粕 (159985), 有色 (159980)
   - 增强与对冲工具: 可转债 (低回撤替代), 纳指/标普 QDII (全球对冲)
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional


class MacroCycleEngine:
    """宏观周期判定与资产配置权重倾斜引擎."""

    def __init__(
        self,
        assets: List[str] = None,
        high_conviction_threshold: float = 0.8,
        mwu_learning_rate: float = 0.05,
    ):
        self.assets = assets or [
            "Equity_CN",   # 沪深300 / 中证500
            "Equity_US",   # 纳斯达克100 / 标普500 (QDII)
            "Bond_Long",   # 10Y / 30Y 国债 ETF
            "Bond_Short",  # 短债 / 货币 ETF
            "Commodity",   # 黄金 / 工业品
            "Convertible", # 可转债
        ]
        self.threshold = high_conviction_threshold
        self.eta = mwu_learning_rate
        self.asset_weights = np.ones(len(self.assets)) / len(self.assets)

    def calculate_macro_scores(
        self,
        pmi: float,
        pmi_prev: float,
        m1_growth: float,
        m2_growth: float,
        credit_pulse: float,
        cpi: float,
        ppi: float,
        ten_year_yield_change: float,
    ) -> Tuple[float, float]:
        """计算宏观增长分与通胀分 (归一化到 [0, 1]).
        
        增长分 (Growth Score):
        - PMI 动量 (PMI - PMI_prev)
        - M1-M2 剪刀差 (M1 - M2)
        - 社融脉冲 (Credit Pulse)
        - 10年国债收益率变动
        """
        # 1. 增长信号聚合
        pmi_momentum = np.tanh((pmi - pmi_prev) / 1.5)
        m1_m2_scissors = np.tanh((m1_growth - m2_growth) / 3.0)
        yield_momentum = np.tanh(ten_year_yield_change / 0.2)
        growth_raw = 0.35 * pmi_momentum + 0.35 * m1_m2_scissors + 0.20 * credit_pulse + 0.10 * yield_momentum
        growth_score = float(1.0 / (1.0 + np.exp(-3.0 * growth_raw)))

        # 2. 通胀信号聚合
        cpi_ppi_gap = np.tanh((ppi - cpi) / 2.0)
        inflation_raw = 0.6 * ppi + 0.4 * cpi_ppi_gap
        inflation_score = float(1.0 / (1.0 + np.exp(-2.5 * inflation_raw)))

        return growth_score, inflation_score

    def trend_and_adx_filter(
        self,
        prices: pd.Series,
        window_fast: int = 30,
        window_slow: int = 60,
    ) -> Tuple[int, bool]:
        """MA30/MA60 双均线交叉与趋势确认.
        
        返回值:
        - trend_direction: 1 (多头排列), -1 (空头排列), 0 (震荡)
        - is_strong_trend: 是否为强趋势行情
        """
        if len(prices) < window_slow:
            return 0, False
            
        ma_fast = prices.rolling(window_fast).mean().iloc[-1]
        ma_slow = prices.rolling(window_slow).mean().iloc[-1]
        
        # 简化版高低波幅计算趋势强弱
        high = prices.rolling(14).max().iloc[-1]
        low = prices.rolling(14).min().iloc[-1]
        diff = (high - low) / (prices.iloc[-1] + 1e-8)
        is_strong = bool(diff > 0.05 and abs(ma_fast - ma_slow) / ma_slow > 0.01)

        if ma_fast > ma_slow:
            return 1, is_strong
        elif ma_fast < ma_slow:
            return -1, is_strong
        return 0, False

    def shift_risk_budget(
        self,
        base_erc_weights: Dict[str, float],
        growth_score: float,
        inflation_score: float,
        lpr_cut_prob: float = 0.0,
    ) -> Dict[str, float]:
        """结合宏观四象限打分与 LPR 降息概率，对基础 ERC 权重进行动态风险预算倾斜.
        
        四象限映射逻辑:
        - 增长上行 + 通胀上行 (再通胀): 超配商品 (黄金/有色), 超配权益顺周期, 低配长债
        - 增长上行 + 通胀下行 (复苏繁荣): 超配权益 (A股/美股), 标配长债, 标配转债
        - 增长下行 + 通胀下行 (通缩衰退): 顶配长债/短债, 低配商品与周期权益; 若 LPR 降息概率极高, 进一步加大长债久期
        - 增长下行 + 通胀上行 (滞胀危机): 顶配商品与现金缓冲, 严格低配权益与信用债
        """
        weights = base_erc_weights.copy()
        
        # 偏离系数调整 (Tilt multipliers)
        tilts = {asset: 1.0 for asset in self.assets}
        
        # 1. 经济增长倾斜
        if growth_score >= self.threshold:
            tilts["Equity_CN"] *= 1.4
            tilts["Equity_US"] *= 1.3
            tilts["Convertible"] *= 1.2
            tilts["Bond_Long"] *= 0.7
        elif growth_score <= (1.0 - self.threshold):
            tilts["Equity_CN"] *= 0.6
            tilts["Equity_US"] *= 0.7
            tilts["Bond_Long"] *= 1.4
            tilts["Bond_Short"] *= 1.3

        # 2. 通胀周期倾斜
        if inflation_score >= self.threshold:
            tilts["Commodity"] *= 1.5
            tilts["Bond_Long"] *= 0.6
        elif inflation_score <= (1.0 - self.threshold):
            tilts["Commodity"] *= 0.7
            tilts["Bond_Long"] *= 1.3

        # 3. RateOracle 降息预警注入 (若 Shibor-LPR 利差预警降息概率超 0.95)
        if lpr_cut_prob >= 0.95:
            tilts["Bond_Long"] *= 1.35
            tilts["Convertible"] *= 1.15

        # 将倾斜系数乘入基础 ERC 权重并重新归一化
        new_weights = {}
        for asset in self.assets:
            new_weights[asset] = weights.get(asset, 1.0 / len(self.assets)) * tilts[asset]
            
        total = sum(new_weights.values())
        return {k: v / total for k, v in new_weights.items()}

    def update_mwu_weights(self, asset_losses: Dict[str, float]):
        """乘法权重更新 (Multiplicative Weights Update) - 动态惩罚表现落后的资产/信号."""
        new_weights = []
        for i, asset in enumerate(self.assets):
            loss = asset_losses.get(asset, 0.0)
            # 指数衰减: w_{t+1} = w_t * exp(-eta * loss)
            w = self.asset_weights[i] * np.exp(-self.eta * loss)
            new_weights.append(w)
        new_weights = np.array(new_weights)
        self.asset_weights = new_weights / np.sum(new_weights)
        return dict(zip(self.assets, self.asset_weights))
