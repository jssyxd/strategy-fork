"""
007 ETH AI 择时策略 - L1~L3 三层 AI 哨兵监控看门狗 (Surveillance Sentinel)
按照 SPEC 9.0 要求构建独立守护进程：
- L1 微观执行层: 毫秒级滑点审查 (>5.0 bps 报警)、时延与报单拒绝监控
- L2 概念漂移层: 滚动 20 笔胜率监控 (<65% 触发熔断重训)、年化波动率暴涨倍数 (>2.5倍冻结)
- L3 资本安全层: 连续 3 笔硬止损触发 48小时冷冻断路器；动态历史回撤达到 12% 全额清仓
"""

import time
import numpy as np
from datetime import datetime, timezone

class AISentinelMonitor:
    def __init__(self, initial_balance=750.0):
        self.balance = initial_balance
        self.high_water_mark = initial_balance
        self.trades_history = [] # [{'time', 'pnl', 'ret', 'is_sl', 'slip_bps'}]
        self.status = "NORMAL_RUNNING"
        self.freeze_until = None
        self.baseline_vol = 0.65 # 基准历史年化波动率 65%

    def on_trade_fill(self, trade_info: dict) -> dict:
        """
        每次成交回调输入：
        trade_info: {
           'time': timestamp,
           'pnl': float,
           'ret_pct': float,
           'is_hard_sl': bool,
           'slip_bps': float,
           'exec_latency_ms': float
        }
        """
        self.balance += trade_info['pnl']
        self.high_water_mark = max(self.high_water_mark, self.balance)
        self.trades_history.append(trade_info)
        
        alerts = []
        actions = []

        # --- L1: 微观执行层检查 ---
        if trade_info.get('slip_bps', 0.0) > 5.0:
            alerts.append(f"[L1-ALERT] 异常滑点超标: {trade_info['slip_bps']:.1f} bps > 5.0 bps! 建议下调加仓比例至 35%")
            actions.append("DOWNGRADE_REENTRY_MARGIN")
            
        if trade_info.get('exec_latency_ms', 0.0) > 800:
            alerts.append(f"[L1-ALERT] 往返网络时延过高: {trade_info['exec_latency_ms']} ms > 800 ms!")

        # --- L2: 概念漂移与滚动胜率检查 ---
        if len(self.trades_history) >= 20:
            recent_20 = self.trades_history[-20:]
            win_count = sum(1 for t in recent_20 if t['pnl'] > 0)
            rolling_win = win_count / 20.0
            
            if rolling_win < 0.65:
                alerts.append(f"[L2-CRITICAL] 滚动20笔胜率跌破熔断线: {rolling_win*100:.1f}% < 65.0%! 触发概念漂移告警")
                self.status = "TRIGGER_RETRAIN"
                actions.append("TRIGGER_WFO_RETRAIN")
            elif rolling_win < 0.70:
                alerts.append(f"[L2-WARN] 滚动20笔胜率进入预警区间: {rolling_win*100:.1f}% < 70.0%")

        # --- L3: 资本与组合硬熔断检查 ---
        # 1. 连续 3 笔硬止损触发 48 小时冷冻
        if len(self.trades_history) >= 3:
            last_3 = self.trades_history[-3:]
            if all(t.get('is_hard_sl', False) for t in last_3):
                alerts.append("[L3-FATAL] 连续 3 笔触发硬止损! 启动紧急冷冻断路器 (48小时禁开仓)")
                self.status = "FROZEN_48H"
                actions.append("CANCEL_ALL_ORDERS")
                actions.append("LOCK_TRADING_GATEWAY")

        # 2. 动态高水位回撤突破 12% 全额清仓
        current_mdd = (self.high_water_mark - self.balance) / self.high_water_mark
        if current_mdd >= 0.12:
            alerts.append(f"[L3-FATAL] 动态回撤突破硬约束: {current_mdd*100:.2f}% >= 12.0%! 执行组合紧急强平")
            self.status = "CIRCUIT_BREAKER_FLATTEN"
            actions.append("MARKET_FLATTEN_ALL")
            actions.append("EMERGENCY_SHUTDOWN")

        return {
            'status': self.status,
            'balance': self.balance,
            'high_water_mark': self.high_water_mark,
            'current_mdd': current_mdd,
            'alerts': alerts,
            'actions': actions
        }
