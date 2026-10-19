"""
006 ETH AI AlphaEvolve Q-Learning 策略 - 离线演化搜索与向量化回测引擎
复刻技术栈：PyTorch / Vectorbt 矩阵回测 / AutoML-Zero / AlphaEvolve GP
"""

import numpy as np
import pandas as pd
import random

class AlphaEvolveQEngine:
    def __init__(self, gamma=0.88, w_imb=2.20, w_break=1.10, th_50=0.60, th_75=1.00,
                 sl_atr_mult=2.5, trail_atr_mult=2.0, fee_rate=0.0005):
        self.gamma = gamma
        self.w_imb = w_imb
        self.w_break = w_break
        self.th_50 = th_50
        self.th_75 = th_75
        self.sl_atr_mult = sl_atr_mult
        self.trail_atr_mult = trail_atr_mult
        self.fee_rate = fee_rate

    def extract_features(self, df):
        close = df['close'].values
        open_ = df['open'].values
        high = df['high'].values
        low = df['low'].values
        vol = df['volume'].values

        # 1. ATR 真实波幅
        tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
        tr = np.insert(tr, 0, high[0] - low[0])
        atr = pd.Series(tr).rolling(14).mean().bfill().values

        # 2. 微观买卖盘失衡代理 (Candle Shape Imbalance)
        hl_span = high - low + 1e-6
        body = close - open_
        imbalance = body / hl_span

        # 3. 局部区间突破 (Breakout)
        hh12 = pd.Series(high).rolling(12).max().bfill().values
        ll12 = pd.Series(low).rolling(12).min().bfill().values
        breakout = (close - ll12) / (hh12 - ll12 + 1e-6) - 0.5

        # 4. 伪 Q-Learning 状态加权衰减累积 (State Value Update)
        raw_reward = self.w_imb * imbalance + self.w_break * breakout
        state = np.zeros_like(close)
        for t in range(1, len(close)):
            state[t] = self.gamma * state[t-1] + (1.0 - self.gamma) * raw_reward[t]

        return close, high, low, atr, state

    def backtest(self, df):
        close, high, low, atr, state = self.extract_features(df)
        cash = 10000.0
        pos = 0 # 1=Long, -1=Short, 0=Flat
        pos_size = 0.0
        entry_price = 0.0
        extreme_price = 0.0
        trades = []
        equity = []

        for i in range(len(close)):
            cp, hp, lp, curr_atr, s = close[i], high[i], low[i], atr[i], state[i]

            # 盘中离场检测
            if pos == 1:
                extreme_price = max(extreme_price, hp)
                # 追踪止盈
                if lp <= extreme_price - self.trail_atr_mult * curr_atr:
                    ep = extreme_price - self.trail_atr_mult * curr_atr
                    cash += pos_size * ep * (1.0 - self.fee_rate)
                    trades.append((ep - entry_price) / entry_price)
                    pos = 0
                # 硬止损
                elif lp <= entry_price - self.sl_atr_mult * curr_atr:
                    ep = entry_price - self.sl_atr_mult * curr_atr
                    cash += pos_size * ep * (1.0 - self.fee_rate)
                    trades.append((ep - entry_price) / entry_price)
                    pos = 0
            elif pos == -1:
                extreme_price = min(extreme_price, lp)
                if hp >= extreme_price + self.trail_atr_mult * curr_atr:
                    ep = extreme_price + self.trail_atr_mult * curr_atr
                    cash += (entry_price - ep) * pos_size + pos_size * entry_price * (1.0 - self.fee_rate)
                    trades.append((entry_price - ep) / entry_price)
                    pos = 0
                elif hp >= entry_price + self.sl_atr_mult * curr_atr:
                    ep = entry_price + self.sl_atr_mult * curr_atr
                    cash += (entry_price - ep) * pos_size + pos_size * entry_price * (1.0 - self.fee_rate)
                    trades.append((entry_price - ep) / entry_price)
                    pos = 0

            # K线收盘建仓
            if pos == 0:
                # 多头
                if s > self.th_75:
                    alloc = cash * 0.75
                    pos_size = (alloc * (1.0 - self.fee_rate)) / cp
                    cash -= alloc
                    pos = 1
                    entry_price = cp
                    extreme_price = cp
                elif s > self.th_50:
                    alloc = cash * 0.50
                    pos_size = (alloc * (1.0 - self.fee_rate)) / cp
                    cash -= alloc
                    pos = 1
                    entry_price = cp
                    extreme_price = cp
                # 空头
                elif s < -self.th_75:
                    alloc = cash * 0.75
                    pos_size = (alloc * (1.0 - self.fee_rate)) / cp
                    cash -= alloc
                    pos = -1
                    entry_price = cp
                    extreme_price = cp
                elif s < -self.th_50:
                    alloc = cash * 0.50
                    pos_size = (alloc * (1.0 - self.fee_rate)) / cp
                    cash -= alloc
                    pos = -1
                    entry_price = cp
                    extreme_price = cp

            cur_eq = cash + (pos_size * cp if pos == 1 else (entry_price - cp) * pos_size + pos_size * entry_price if pos == -1 else 0.0)
            equity.append(cur_eq)

        eq = np.array(equity)
        tot_ret = (eq[-1] - 10000.0) / 10000.0
        peak = np.maximum.accumulate(eq)
        max_dd = np.max((peak - eq) / peak)
        win_rate = np.mean([t > 0 for t in trades]) if len(trades) > 0 else 0.0

        return {
            'total_return': tot_ret,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'trade_count': len(trades)
        }
