"""formula_factor_bank.py - 结合同花顺 10k SFT 指标公式库与 Alpha101 的公式化截面因子库.

基于 Hugging Face 数据集 `tonghuashun_code_sft_10k` 与 `AlphaFactory`：
将同花顺经典技术面指标（箱体震荡极值、筹码锁仓突破、多空均线剪刀差）转换为纯矢量化 Pandas/Polars 因子计算函数。
"""

import numpy as np
import pandas as pd


class FormulaFactorBank:
    """技术指标与截面公式因子生成器."""

    @staticmethod
    def dynamic_box_oscillator(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 20) -> pd.Series:
        """动态箱体震荡与突破因子 (对应 tonghuashun UPPER:HHV(H,N), LOWER:LLV(L,N))."""
        upper = high.rolling(n).max()
        lower = low.rolling(n).min()
        mid = (upper + lower) / 2.0
        # 因子值: 当前价格在箱体内的百分比相对位置
        box_pos = (close - lower) / (upper - lower + 1e-8)
        return box_pos

    @staticmethod
    def dual_ma_scissors(close: pd.Series, fast: int = 5, slow: int = 20) -> pd.Series:
        """多空均线剪刀差与动量加速度."""
        ma_fast = close.rolling(fast).mean()
        ma_slow = close.rolling(slow).mean()
        return (ma_fast - ma_slow) / (ma_slow + 1e-8)

    @staticmethod
    def volume_price_divergence(close: pd.Series, volume: pd.Series, n: int = 10) -> pd.Series:
        """量价背离因子: 价格涨幅与成交量增幅的偏离."""
        ret = close.pct_change(n)
        vol_change = volume.pct_change(n)
        return ret - vol_change
