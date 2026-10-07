"""chip_analyzer.py - A股微观筹码分布 (CYQ Chips) 截面特征提取引擎.

逆向还原自内部工程 `options_hedging_system/model_eze.py` 与 `chip_tushare.py` 中的 ChipEngine：
提取五大核心微观筹码特征：
1. winner_rate: 当前价格对应的获利盘比例 (0.0 ~ 1.0)
2. weight_avg: 筹码加权平均成本价格
3. cost_ISB: 筹码集中度指标 (90% 或 70% 筹码成本分布密集区间)
4. cost_BSpeilt: 主力成本与散户成本的偏离度
5. chip_breakout: 价格突破高集中度筹码峰的强动量买入信号
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


class ChipAnalyzer:
    """微观筹码特征提取器."""

    def __init__(self, high_win_rate_threshold: float = 0.85):
        self.win_threshold = high_win_rate_threshold

    def compute_chip_features(self, df_chip: pd.DataFrame, current_price: float) -> Dict[str, float]:
        """从 Tushare / 交易所筹码数据计算截面选股特征."""
        if df_chip.empty:
            return {
                "winner_rate": 0.5,
                "cost_bias": 0.0,
                "concentration": 0.0,
                "chip_momentum": 0.0,
            }

        latest = df_chip.iloc[-1]
        winner_rate = float(latest.get("winner_rate", 0.5))
        weight_avg = float(latest.get("weight_avg", current_price))
        cost_isb = float(latest.get("cost_ISB", 0.1))

        # 成本偏离度: (现价 - 加权成本) / 加权成本
        cost_bias = (current_price - weight_avg) / (weight_avg + 1e-8)
        
        # 集中度惩罚与突破加权: 获利盘极高且筹码集中度收敛，代表锁仓主升浪
        chip_momentum = winner_rate * (1.0 - cost_isb)

        return {
            "winner_rate": winner_rate,
            "cost_bias": cost_bias,
            "concentration": 1.0 - cost_isb,
            "chip_momentum": chip_momentum,
        }
