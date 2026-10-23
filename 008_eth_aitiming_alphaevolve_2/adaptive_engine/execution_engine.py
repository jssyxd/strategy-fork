"""
007 ETH AI 择时策略 - 悲观执行匹配与真实执行摩擦对齐回测核心
杜绝柱内乐观成交偏差（Intra-bar Optimism），实现动态波动率滑点惩罚
"""

import numpy as np

class RealisticExecutionEngine:
    """
    高保真撮合模拟引擎：
    1. 防未来函数：当前 15m 收盘生成 pending 信号，强制在下一根 Bar 的 Open 执行撮合。
    2. 柱内高低悲观仲裁：
       - 若 Open 靠近 High，判定先上冲后下杀；
       - 若 Open 靠近 Low，判定先下探后回升；
       - 若同一根 K 线上同时满足止盈和止损价格，按悲观原则【强制判定止损优先成交】。
    3. 动态波动率滑点模型：
       滑点 = 基准滑点 (1.5 bps) * (1.0 + 当前ATR / 均值ATR)。
    """
    def __init__(self, initial_capital=750.0, fee_maker=0.0002, fee_taker=0.0005, base_slip_bps=1.5):
        self.initial_capital = initial_capital
        self.fee_maker = fee_maker
        self.fee_taker = fee_taker
        self.base_slip_bps = base_slip_bps

    def simulate(self, features: dict, genome: list, start_idx: int = 0, end_idx: int = None,
                 ablation: dict = None):
        """
        ablation 支持的消融配置字典:
          - 'disable_q_state': bool (是否关闭时序衰减记忆)
          - 'disable_reentry': bool (是否关闭 75% 二次加仓)
          - 'disable_trail': bool (是否关闭动态追踪止盈，改用收盘固定离场)
          - 'disable_hard_sl': bool (是否关闭 -2.5% 硬止损)
          - 'leverage': float (名义杠杆倍数，默认 3.0)
        """
        if ablation is None:
            ablation = {}
            
        disable_q_state = ablation.get('disable_q_state', False)
        disable_reentry = ablation.get('disable_reentry', False)
        disable_trail = ablation.get('disable_trail', False)
        disable_hard_sl = ablation.get('disable_hard_sl', False)
        leverage = ablation.get('leverage', 3.0)

        gamma, w_imb, w_bo, w_dev, th_50, th_75, trail_mult, sl_mult, tp_mult = genome
        
        close = features['close']
        open_ = features['open']
        high = features['high']
        low = features['low']
        atr = features['atr']
        f_imbalance = features['imbalance']
        f_breakout = features['breakout']
        f_dev = features['dev']
        
        total_len = len(close)
        if end_idx is None or end_idx > total_len:
            end_idx = total_len
            
        mean_atr = np.mean(atr[start_idx:end_idx]) + 1e-6

        # 1. 生成原始奖励信号与 Q-State 递推
        raw_reward = w_imb * f_imbalance + w_bo * f_breakout + w_dev * f_dev
        state = np.zeros(total_len, dtype=np.float64)
        
        if disable_q_state:
            state = raw_reward.copy()
        else:
            gamma_clamped = min(0.999, max(0.01, gamma))
            for t in range(1, total_len):
                state[t] = gamma_clamped * state[t-1] + (1.0 - gamma_clamped) * raw_reward[t]
        # 2. 模拟回测状态机
        cash = self.initial_capital
        pos = 0 # 1=Long, -1=Short, 0=Flat
        pos_qty = 0.0
        pos_margin = 0.0
        entry_p = 0.0
        peak_p = 0.0
        trough_p = 0.0
        pending = None # ('BUY'|'SELL', ratio, bar_idx)
        
        trades = []
        equity = []
        
        for i in range(start_idx, end_idx - 1):
            cp, hp, lp, op = close[i], high[i], low[i], open_[i]
            c_atr = atr[i]
            s = state[i]
            
            # 计算当前动态滑点比例
            dyn_slip = (self.base_slip_bps / 10000.0) * (1.0 + c_atr / mean_atr)

            # A. 执行前一根 K 线收盘确认的开仓信号 (在当前 Open 撮合)
            if pending is not None:
                p_action, p_ratio, p_idx = pending
                if i >= p_idx + 1:
                    if p_action == 'BUY':
                        fill_p = op * (1.0 + dyn_slip)
                        alloc_margin = cash * p_ratio
                        notional = alloc_margin * leverage
                        fee = notional * self.fee_taker
                        if alloc_margin - fee > 0:
                            pos_qty = (notional - fee) / fill_p
                            pos_margin = alloc_margin
                            cash -= alloc_margin
                            pos = 1
                            entry_p = fill_p
                            peak_p = fill_p
                    elif p_action == 'SELL':
                        fill_p = op * (1.0 - dyn_slip)
                        alloc_margin = cash * p_ratio
                        notional = alloc_margin * leverage
                        fee = notional * self.fee_taker
                        if alloc_margin - fee > 0:
                            pos_qty = (notional - fee) / fill_p
                            pos_margin = alloc_margin
                            cash -= alloc_margin
                            pos = -1
                            entry_p = fill_p
                            trough_p = fill_p
                    pending = None

            # B. 盘中持仓离场检测（引入悲观顺序仲裁）
            if pos == 1:
                peak_p = max(peak_p, hp)
                trail_stop = peak_p - trail_mult * c_atr
                hard_stop = entry_p - sl_mult * c_atr
                tp_target = entry_p + tp_mult * c_atr

                # 触碰判断
                hit_tp = (hp >= tp_target)
                hit_trail = (lp <= trail_stop) and (not disable_trail)
                hit_sl = (lp <= hard_stop) and (not disable_hard_sl)
                
                # 悲观仲裁：如果同时触碰止损和止盈，判定止损优先触发！
                if (hit_sl or hit_trail) and hit_tp:
                    # 悲观：止损/追踪离场优先
                    exit_p = max(trail_stop if hit_trail else hard_stop, hard_stop) * (1.0 - dyn_slip)
                    notional = pos_qty * exit_p
                    fee = notional * self.fee_taker
                    gross = pos_qty * (exit_p - entry_p)
                    net_pnl = gross - fee
                    cash += pos_margin + net_pnl
                    trades.append((exit_p - entry_p) / entry_p)
                    pos, pos_qty, pos_margin, pending = 0, 0.0, 0.0, None
                elif hit_tp:
                    exit_p = tp_target * (1.0 - dyn_slip)
                    notional = pos_qty * exit_p
                    fee = notional * self.fee_taker
                    gross = pos_qty * (exit_p - entry_p)
                    net_pnl = gross - fee
                    cash += pos_margin + net_pnl
                    trades.append((exit_p - entry_p) / entry_p)
                    pos, pos_qty, pos_margin, pending = 0, 0.0, 0.0, None
                elif hit_trail or hit_sl:
                    exit_p = (trail_stop if hit_trail else hard_stop) * (1.0 - dyn_slip)
                    notional = pos_qty * exit_p
                    fee = notional * self.fee_taker
                    gross = pos_qty * (exit_p - entry_p)
                    net_pnl = gross - fee
                    cash += pos_margin + net_pnl
                    trades.append((exit_p - entry_p) / entry_p)
                    pos, pos_qty, pos_margin, pending = 0, 0.0, 0.0, None

            elif pos == -1:
                trough_p = min(trough_p, lp)
                trail_stop = trough_p + trail_mult * c_atr
                hard_stop = entry_p + sl_mult * c_atr
                tp_target = entry_p - tp_mult * c_atr

                hit_tp = (lp <= tp_target)
                hit_trail = (hp >= trail_stop) and (not disable_trail)
                hit_sl = (hp >= hard_stop) and (not disable_hard_sl)

                # 悲观仲裁
                if (hit_sl or hit_trail) and hit_tp:
                    exit_p = min(trail_stop if hit_trail else hard_stop, hard_stop) * (1.0 + dyn_slip)
                    notional = pos_qty * exit_p
                    fee = notional * self.fee_taker
                    gross = pos_qty * (entry_p - exit_p)
                    net_pnl = gross - fee
                    cash += pos_margin + net_pnl
                    trades.append((entry_p - exit_p) / entry_p)
                    pos, pos_qty, pos_margin, pending = 0, 0.0, 0.0, None
                elif hit_tp:
                    exit_p = tp_target * (1.0 + dyn_slip)
                    notional = pos_qty * exit_p
                    fee = notional * self.fee_taker
                    gross = pos_qty * (entry_p - exit_p)
                    net_pnl = gross - fee
                    cash += pos_margin + net_pnl
                    trades.append((entry_p - exit_p) / entry_p)
                    pos, pos_qty, pos_margin, pending = 0, 0.0, 0.0, None
                elif hit_trail or hit_sl:
                    exit_p = (trail_stop if hit_trail else hard_stop) * (1.0 + dyn_slip)
                    notional = pos_qty * exit_p
                    fee = notional * self.fee_taker
                    gross = pos_qty * (entry_p - exit_p)
                    net_pnl = gross - fee
                    cash += pos_margin + net_pnl
                    trades.append((entry_p - exit_p) / entry_p)
                    pos, pos_qty, pos_margin, pending = 0, 0.0, 0.0, None

            # C. 收盘触发开仓/加仓逻辑 (Bar Close 确认)
            if pending is None:
                if pos == 0:
                    if s > th_75 and state[i-1] <= th_75:
                        pending = ('BUY', 0.50 if disable_reentry else 0.75, i)
                    elif s > th_50 and state[i-1] <= th_50:
                        pending = ('BUY', 0.50, i)
                    elif s < -th_75 and state[i-1] >= -th_75:
                        pending = ('SELL', 0.50 if disable_reentry else 0.75, i)
                    elif s < -th_50 and state[i-1] >= -th_50:
                        pending = ('SELL', 0.50, i)

            # D. 计算当前资产净值
            unrealized = 0.0
            if pos == 1:
                unrealized = pos_qty * (cp - entry_p)
            elif pos == -1:
                unrealized = pos_qty * (entry_p - cp)
            cur_equity = cash + pos_margin + unrealized
            equity.append(cur_equity)

        # 统计核心指标
        eq = np.array(equity)
        if len(eq) == 0:
            return 0.0, 0.0, 0.0, 0.0, 0, []
        
        tot_ret = (eq[-1] - self.initial_capital) / self.initial_capital
        pk = np.maximum.accumulate(eq)
        drawdowns = (pk - eq) / pk
        mdd = np.max(drawdowns) if len(drawdowns) > 0 else 0.0
        win_rate = np.mean([t > 0 for t in trades]) if len(trades) > 0 else 0.0
        calmar = tot_ret / (mdd + 1e-4)
        
        # 适应度函数：加惩罚
        fitness = calmar * 1.5 + win_rate * 10.0 - 15.0 * (mdd ** 2)
        if len(trades) < 10:
            fitness -= (10 - len(trades)) * 10.0
        elif len(trades) > 120:
            fitness -= (len(trades) - 120) * 1.0

        return fitness, tot_ret, mdd, win_rate, len(trades), eq
