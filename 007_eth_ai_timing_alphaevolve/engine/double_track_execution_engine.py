#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双轨执行状态机引擎核心实现 (Double-Track Execution Engine)
严格遵循 SPEC-008 规范：
- Agent 12: 15m 收盘确权 50% 首仓入场状态机 (次根 Open 撮合)
- Agent 13: 15m 收盘确权 75% 顺势二次加仓机 (仓位上限 2 层)
- Agent 14: 盘中微观移动追踪锁盈机 (Trailing Stop)
- Agent 15: -2.50% 物理硬止损拦截机 (Hard Stop)
- Agent 16: 50.5 小时时间止损防横盘磨损机 (Time Stop)
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class Position:
    direction: int = 0       # 1: Long, -1: Short, 0: Flat
    units: float = 0.0       # 持仓币数 (ETH)
    entry_avg_price: float = 0.0 # 持仓加权均价
    order_step: int = 0      # 0: Flat, 1: 50% 首仓, 2: 75% 加仓
    entry_bar_idx: int = 0   # 开仓对应的 Bar 索引
    peak_price: float = 0.0  # 持仓期间盘中最高价
    valley_price: float = 999999.0 # 持仓期间盘中最低价
    trail_activated: bool = False  # 移动追踪是否已激活

class DoubleTrackExecutionEngine:
    def __init__(
        self,
        th_50: float = 1.288,
        th_75: float = 1.650,
        tp_pct: float = 0.0090,         # +0.90% 激活动态追踪
        sl_pct: float = 0.0250,         # -2.50% 物理硬止损
        trail_callback_pct: float = 0.0006, # 6 bps 盘中极值安全锁盈
        max_hold_bars: int = 202,       # 202 根 15m Bar (50.5小时) 时间止损
        fee_rate: float = 0.0005,       # 5.0 bps 双边 Taker 手续费
        slippage_rate: float = 0.0003   # 3.0 bps 物理冲击与排队滑点
    ):
        self.th_50 = th_50
        self.th_75 = th_75
        self.tp_pct = tp_pct
        self.sl_pct = sl_pct
        self.trail_cb = trail_callback_pct
        self.max_hold = max_hold_bars
        self.fee = fee_rate
        self.slippage = slippage_rate

    def check_intraday_exits(self, pos: Position, high: float, low: float, bar_idx: int) -> Optional[Dict[str, Any]]:
        """
        盘中极值连续出场检测 (连续 Tick / 1m 极值)
        优先级：硬止损 > 移动追踪锁盈 > 时间止损
        """
        if pos.direction == 0:
            return None

        # 多头持仓管理
        if pos.direction == 1:
            pos.peak_price = max(pos.peak_price, high)
            if (high - pos.entry_avg_price) / pos.entry_avg_price >= self.tp_pct:
                pos.trail_activated = True

            # 1. 物理硬止损拦截
            hard_stop_price = pos.entry_avg_price * (1.0 - self.sl_pct)
            if low <= hard_stop_price:
                exit_fill = hard_stop_price * (1.0 - self.slippage)
                return {
                    "action": "多仓离场",
                    "reason": "R-EXIT-HARD-STOP",
                    "fill_price": exit_fill,
                    "desc": "【规则-R-EXIT-HARD-STOP】盘中跌破-2.50%物理防线，市价全平硬止损"
                }

            # 2. 动态移动追踪锁盈
            if pos.trail_activated:
                trail_stop_price = pos.peak_price * (1.0 - self.trail_cb)
                if low <= trail_stop_price:
                    exit_fill = trail_stop_price * (1.0 - self.slippage)
                    return {
                        "action": "多仓离场",
                        "reason": "R-EXIT-TRAIL-LONG",
                        "fill_price": exit_fill,
                        "desc": "【规则-R-EXIT-TRAIL-LONG】盘中冲高回撤达到保护阈值，市价全平动态锁盈"
                    }

            # 3. 50.5 小时时间止损
            if (bar_idx - pos.entry_bar_idx) >= self.max_hold:
                exit_fill = low * (1.0 - self.slippage) # 保守以低点撮合
                return {
                    "action": "多仓离场",
                    "reason": "R-EXIT-TIME-STOP",
                    "fill_price": exit_fill,
                    "desc": "【规则-R-EXIT-TIME-STOP】持仓满 202 根 Bar (50.5h) 未达标，主动市价强平"
                }

        # 空头持仓管理
        elif pos.direction == -1:
            pos.valley_price = min(pos.valley_price, low)
            if (pos.entry_avg_price - low) / pos.entry_avg_price >= self.tp_pct:
                pos.trail_activated = True

            # 1. 物理硬止损拦截
            hard_stop_price = pos.entry_avg_price * (1.0 + self.sl_pct)
            if high >= hard_stop_price:
                exit_fill = hard_stop_price * (1.0 + self.slippage)
                return {
                    "action": "空仓离场",
                    "reason": "R-EXIT-HARD-STOP",
                    "fill_price": exit_fill,
                    "desc": "【规则-R-EXIT-HARD-STOP】盘中上穿+2.50%物理防线，市价全平硬止损"
                }

            # 2. 动态移动追踪锁盈
            if pos.trail_activated:
                trail_stop_price = pos.valley_price * (1.0 + self.trail_cb)
                if high >= trail_stop_price:
                    exit_fill = trail_stop_price * (1.0 + self.slippage)
                    return {
                        "action": "空仓离场",
                        "reason": "R-EXIT-TRAIL-SHORT",
                        "fill_price": exit_fill,
                        "desc": "【规则-R-EXIT-TRAIL-SHORT】盘中探底反弹达到保护阈值，市价全平动态锁盈"
                    }

            # 3. 50.5 小时时间止损
            if (bar_idx - pos.entry_bar_idx) >= self.max_hold:
                exit_fill = high * (1.0 + self.slippage)
                return {
                    "action": "空仓离场",
                    "reason": "R-EXIT-TIME-STOP",
                    "fill_price": exit_fill,
                    "desc": "【规则-R-EXIT-TIME-STOP】持仓满 202 根 Bar (50.5h) 未达标，主动市价强平"
                }

        return None

    def evaluate_bar_close_entry(self, pos: Position, s_val: float) -> Optional[Dict[str, Any]]:
        """
        15m BarClose 确权入场决策 (次根 Bar 开盘撮合)
        """
        # 1. 50% 首仓试探入场机 (Agent 12)
        if pos.direction == 0:
            if s_val > self.th_50:
                return {
                    "action": "多仓进场",
                    "amount_ratio": 0.50,
                    "target_direction": 1,
                    "target_step": 1,
                    "desc": "【规则-R-ENTRY-LONG-50】15m收盘S_t突破+Th_50，次根开盘建立50%可用资金试探多头"
                }
            elif s_val < -self.th_50:
                return {
                    "action": "空仓进场",
                    "amount_ratio": 0.50,
                    "target_direction": -1,
                    "target_step": 1,
                    "desc": "【规则-R-ENTRY-SHORT-50】15m收盘S_t突破-Th_50，次根开盘建立50%可用资金试探空头"
                }

        # 2. 75% 顺势二次加仓机 (Agent 13, 仓位上限 2)
        elif pos.order_step == 1:
            if pos.direction == 1 and s_val > self.th_75:
                return {
                    "action": "多仓进场",
                    "amount_ratio": 0.75,
                    "target_direction": 1,
                    "target_step": 2,
                    "desc": "【规则-R-ENTRY-LONG-75】15m收盘S_t突破+Th_75极值，次根开盘以剩余资金75%顺势重仓加多"
                }
            elif pos.direction == -1 and s_val < -self.th_75:
                return {
                    "action": "空仓进场",
                    "amount_ratio": 0.75,
                    "target_direction": -1,
                    "target_step": 2,
                    "desc": "【规则-R-ENTRY-SHORT-75】15m收盘S_t突破-Th_75极值，次根开盘以剩余资金75%顺势重仓加空"
                }

        return None
