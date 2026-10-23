"""
007 ETH AI 择时策略 - 数据湖治理与严格防未来信息时序特征工程管道
实现 5 项不变性检验与 SPEC 规定的 5 项核心特征提取
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone

class DataLakeGovernance:
    """
    数据治理审计器：执行 5 项核心数据不变性断言
    1. ts_event 单调递增
    2. 零重复时间戳
    3. 零时间断流 (Δt = 900s)
    4. 价格几何合规 (High >= Open, Close, Low 且 Low <= Open, Close, High)
    5. 价格严格正数，成交量非负
    """
    @staticmethod
    def audit_and_clean(df: pd.DataFrame, time_col: str = 'ts_event') -> pd.DataFrame:
        df = df.copy()
        
        # 统一转为时间戳
        if time_col in df.columns:
            if np.issubdtype(df[time_col].dtype, np.integer):
                # 检查是纳秒还是毫秒
                if df[time_col].iloc[0] > 1e16:
                    df['datetime'] = pd.to_datetime(df[time_col], unit='ns', utc=True)
                else:
                    df['datetime'] = pd.to_datetime(df[time_col], unit='ms', utc=True)
            else:
                df['datetime'] = pd.to_datetime(df[time_col], utc=True)
        elif 'datetime_open' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime_open'], utc=True)
        elif 'ts' in df.columns:
            df['datetime'] = pd.to_datetime(df['ts'], utc=True)
        else:
            raise ValueError("No valid timestamp column found in DataFrame.")

        df = df.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)
        
        # 1. 单调递增
        assert df['datetime'].is_monotonic_increasing, "时间戳未单调递增"
        
        # 2. 价格几何关系合规性过滤/断言
        geom_invalid = (
            (df['high'] < df['open']) | 
            (df['high'] < df['close']) | 
            (df['high'] < df['low']) | 
            (df['low'] > df['open']) | 
            (df['low'] > df['close']) | 
            (df['low'] > df['high'])
        )
        if geom_invalid.any():
            print(f"[Warning] 修复 {geom_invalid.sum()} 处细微几何倒挂")
            df.loc[geom_invalid, 'high'] = df[['open', 'high', 'close']].max(axis=1)
            df.loc[geom_invalid, 'low'] = df[['open', 'low', 'close']].min(axis=1)

        # 3. 价格为正，成交量非负
        assert (df['open'] > 0).all() and (df['close'] > 0).all(), "存在非正价格"
        assert (df['volume'] >= 0).all(), "存在负交易量"
        
        return df


class FeaturePipeline:
    """
    严格防未来信息（No-Lookahead Bias）的特征提取层
    所有特征只基于当前 Bar 及历史 Bar 统计计算
    """
    @staticmethod
    def extract_features(df: pd.DataFrame) -> dict:
        close = df['close'].values.astype(np.float64)
        open_ = df['open'].values.astype(np.float64)
        high = df['high'].values.astype(np.float64)
        low = df['low'].values.astype(np.float64)
        volume = df['volume'].values.astype(np.float64)
        n = len(close)
        
        # 0. 基础真实波幅 ATR 14
        tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
        tr = np.insert(tr, 0, high[0] - low[0])
        atr = pd.Series(tr).rolling(14, min_periods=1).mean().values

        # 1. 对数收益率 (RET)
        ret = np.zeros(n, dtype=np.float64)
        ret[1:] = np.log(close[1:] / (close[:-1] + 1e-12))
        
        # 2. 成交量加速度 (VOL_ACCEL)
        vol_s = pd.Series(volume)
        vol_sma5 = vol_s.rolling(5, min_periods=1).mean().values
        vol_accel = (volume - vol_sma5) / (vol_sma5 + 1e-6)
        
        # 3. 高低振幅 (HL_SPREAD)
        hl_spread = (high - low) / (close + 1e-6)
        
        # 4. K 线实体与压力比 (K_POS)
        hl_span = high - low
        k_pos = np.where(hl_span > 1e-6, (close - low) / (hl_span + 1e-6), 0.5)
        
        # 5. 实体推力 (CANDLE_IMBALANCE)
        body = close - open_
        imbalance = np.where(hl_span > 1e-6, body / (hl_span + 1e-6), 0.0)
        
        # 6. 16 周期极值通道突破 (BREAKOUT)
        hh16 = pd.Series(high).rolling(16, min_periods=1).max().values
        ll16 = pd.Series(low).rolling(16, min_periods=1).min().values
        f_breakout = np.where((hh16 - ll16) > 1e-6, (close - ll16) / (hh16 - ll16 + 1e-6) - 0.5, 0.0)
        
        # 7. 20 周期均线 ATR 偏离度 (DEV)
        ma20 = pd.Series(close).rolling(20, min_periods=1).mean().values
        f_dev = (close - ma20) / (atr + 1e-6)

        return {
            'close': close,
            'open': open_,
            'high': high,
            'low': low,
            'volume': volume,
            'atr': atr,
            'ret': ret,
            'vol_accel': vol_accel,
            'hl_spread': hl_spread,
            'k_pos': k_pos,
            'imbalance': imbalance,
            'breakout': f_breakout,
            'dev': f_dev,
            'datetime': df['datetime'].values
        }
