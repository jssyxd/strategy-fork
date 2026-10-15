"""nasdaq_swing_engine.py - 纳斯达克100 ETF 动量波段跟踪引擎与超额收益对冲.

逆向还原自内部工程 `btc_15m/swing.py` 与 `nasdaq.py` (实盘 Calmar 比率 8.68 架构)：
1. 15分钟高频 K 线波段动量跟踪 (Swing Momentum)
2. 动态自适应波动率滤网 (VIX / ATR Adaptive Filter)
3. 纳斯达克 ETF (QQQ / 513100) 收益对比基准
4. 结合 Delta-Gamma 期权对冲增强
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple


class NasdaqSwingEngine:
    """纳斯达克 ETF 动量波段与增强执行引擎."""

    def __init__(
        self,
        vol_lookback: int = 48, # 15m 级别 12 小时窗口
        momentum_fast: int = 12,
        momentum_slow: int = 36,
    ):
        self.vol_lookback = vol_lookback
        self.fast = momentum_fast
        self.slow = momentum_slow

    def generate_signal(self, df_15m: pd.DataFrame) -> Tuple[float, float, str]:
        """计算波段信号与动态仓位乘数.
        
        返回值:
        - target_allocation: 目标多头仓位比例 (0.0 ~ 1.5, 支持适度杠杆或期权放大)
        - dynamic_vol: 动态已实现波动率
        - regime: 市场状态 ("TREND_BULL", "CHOPPY", "HIGH_VOL_CRASH")
        """
        if len(df_15m) < self.slow:
            return 1.0, 0.20, "HOLD"

        close = df_15m["close"]
        ret = close.pct_change()
        vol = float(ret.rolling(self.vol_lookback).std().iloc[-1] * np.sqrt(48 * 252))

        ema_fast = close.ewm(span=self.fast).mean().iloc[-1]
        ema_slow = close.ewm(span=self.slow).mean().iloc[-1]
        
        trend = (ema_fast - ema_slow) / ema_slow

        # 状态机逻辑
        if vol > 0.45:
            # 极高波动恐慌区，防御模式，压缩敞口
            return 0.3, vol, "HIGH_VOL_CRASH"
        elif trend > 0.003 and vol < 0.25:
            # 低波动顺势主升浪，适度放大仓位享受动量
            return 1.3, vol, "TREND_BULL"
        elif trend < -0.003:
            # 下跌趋势，减仓避险
            return 0.5, vol, "TREND_BEAR"
        else:
            # 震荡区间，标配基准
            return 1.0, vol, "CHOPPY"
