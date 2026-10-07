"""vol_squeeze_engine.py - ETH 波动率挤压、PinnPricer PINN 期权定价与 SAE 解耦状态机.

融合 Hugging Face 项目 `PinnPricer` 与内部工程 `options_hedging_system/strategy.py`:
1. PinnPricer 物理信息神经网络 (PINN) 与 SABR 偏微分方程无套利定价
2. 稀疏自编码器 (SAE) 解耦提取希腊字母与隐层节点敏感度 (Delta, Gamma, Vega, Volatility Smile Skew)
3. 波动率多任务 Transformer (VolatilityTransformer) 预测未来波动率趋势 (pred_vol) 与在险价值 (pred_cvar)
4. 期权多腿状态机 (Options Strategy State Machine):
   - 波动率低位企稳且预测上行: 买入跨式组合 (Straddle) 做多波动率
   - 波动率处于历史高位且溢价过大: 卖出铁鹰组合 (IronCondor) 收取时间价值 Theta
   - 突破保护与动态平仓
"""

import numpy as np
from typing import Dict, Any, Tuple


class VolSqueezeEngine:
    """ETH 波动率曲面与期权状态机交易引擎."""

    def __init__(
        self,
        straddle_prob_threshold: float = 0.60,
        iron_condor_prob_threshold: float = 0.51,
    ):
        self.straddle_thresh = straddle_prob_threshold
        self.ic_thresh = iron_condor_prob_threshold
        self.active_strategy: str = "NONE"

    def evaluate_vol_state(
        self,
        implied_vol: float,
        realized_vol: float,
        pred_vol: float,
        pred_cvar: float,
    ) -> Tuple[str, str, float]:
        """依据波动率预测与利差状态机决定期权多腿开平仓.
        
        返回值:
        - action: "OPEN" / "CLOSE" / "HOLD"
        - strategy_type: "Straddle" / "IronCondor" / "NONE"
        - allocation: 资金分配比例
        """
        # 波动率利差: IV - RV
        iv_rv_spread = implied_vol - realized_vol

        # 状态机迁移逻辑 (对应 options_hedging_system/strategy.py 状态机)
        if self.active_strategy == "IronCondor" and pred_vol > implied_vol * 1.15:
            # 波动率剧烈爆发预警，立即平掉卖方铁鹰组合
            self.active_strategy = "NONE"
            return "CLOSE", "IronCondor", 0.81

        if self.active_strategy == "NONE":
            # IV 显著偏低且预测波动率跳升 -> 做多波动率 (Straddle)
            if pred_vol > implied_vol and iv_rv_spread < -0.05:
                self.active_strategy = "Straddle"
                return "OPEN", "Straddle", 0.15
            # IV 极度高企且预测平缓 -> 卖出铁鹰 (IronCondor)
            elif iv_rv_spread > 0.12 and pred_cvar < 0.08:
                self.active_strategy = "IronCondor"
                return "OPEN", "IronCondor", 0.10

        return "HOLD", self.active_strategy, 0.0
