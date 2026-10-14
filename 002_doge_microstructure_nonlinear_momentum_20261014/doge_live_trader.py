"""
DOGE 高频微观结构非线性动量生产级实盘与回测运行器 (DOGE Microstructure Nonlinear Momentum Live Trader)

本模块实现了针对 DOGE-USDT-SWAP (永续合约) 与 DOGE-USDT (现货通道) 的统一事件驱动交易执行系统。
融合 9 大微观结构因子提取、深度卷积残差时序模型推理、平方根大单滑点拆分与 POV (Percentage of Volume) 执行算法。
"""

import sys
import os
import time
import math
import logging
from typing import Dict, Any, Optional, Tuple
import numpy as np

# 导入核心组件
from factors import MicrostructureFeatureExtractor
from model import FastNonlinearMomentumInference, TORCH_AVAILABLE
from engine import BacktestEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("DogeLiveTrader")


class DogeMicrostructureStrategy:
    """
    DOGE 微观情绪驱动的高频非线性动量策略核心控制器。
    """
    def __init__(
        self,
        symbol_perp: str = "DOGE-USDT-SWAP",
        symbol_spot: str = "DOGE-USDT",
        initial_capital_cny: float = 15000000.0,
        cny_usd_rate: float = 7.20,
        max_leverage: float = 3.0,
        entry_threshold: float = 0.08,
        burst_threshold: float = 0.28,
        stop_loss_pct: float = 0.025,
        take_profit_trailing_pct: float = 0.045,
        pov_limit: float = 0.15,
        seq_len: int = 24
    ):
        self.symbol_perp = symbol_perp
        self.symbol_spot = symbol_spot
        self.initial_capital_usd = initial_capital_cny / cny_usd_rate
        self.capital_usd = self.initial_capital_usd
        self.max_leverage = max_leverage
        self.entry_threshold = entry_threshold
        self.burst_threshold = burst_threshold
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_trailing_pct = take_profit_trailing_pct
        self.pov_limit = pov_limit
        self.seq_len = seq_len
        
        # 1. 初始化特征提取器与深度学习推理模型
        self.extractor = MicrostructureFeatureExtractor(depth_levels=5, window_fast=12, window_slow=36)
        self.model = FastNonlinearMomentumInference(input_dim=9, seq_len=seq_len, hidden_dim=64, seed=42)
        
        # 2. 状态变量
        self.position_size_coin = 0.0 # 正数为多头，负数为空头
        self.position_channel = None  # 'perp' 或 'spot'
        self.entry_price = 0.0
        self.peak_price = 0.0
        self.consecutive_losses = 0
        self.is_cooling_down = False
        self.cool_down_until = 0.0

        logger.info(
            f"DOGE 高频非线性动量策略初始化完成: 标的={symbol_perp}/{symbol_spot}, "
            f"容量={initial_capital_cny:,.0f} CNY, 杠杆上限={max_leverage:.1f}x, 止损={stop_loss_pct*100:.1f}%, 追踪止盈={take_profit_trailing_pct*100:.1f}%"
        )

    def on_market_bar(self, bar_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        每根微观结构 Bar (1m / 5m) 到达时触发策略逻辑。
        """
        now = time.time()
        if self.is_cooling_down:
            if now < self.cool_down_until:
                logger.debug("处于连续亏损保护冷却期，跳过当前 Bar 评估。")
                return None
            else:
                self.is_cooling_down = False
                logger.info("冷却期结束，重新恢复信号评估。")

        curr_perp_px = bar_data['perp_close']
        curr_spot_px = bar_data['spot_close']
        curr_funding = bar_data.get('funding_rate', 0.0001)
        bar_vol = bar_data.get('bar_vol', 0.0035)
        bar_vol_usd = bar_data.get('volume_usd', 500000.0)

        # 1. 特征提取与模型打分
        features = self.extractor.extract_all(bar_data)
        signals, burst_confs = self.model.predict_sequence(features)
        current_signal = signals[-1]
        current_burst = burst_confs[-1]

        # 2. 持仓平仓与风控检查
        if self.position_size_coin != 0.0:
            return self._manage_active_position(
                curr_perp_px, current_signal, current_burst, bar_vol, bar_vol_usd
            )

        # 3. 开仓机会评估
        if abs(current_signal) > self.entry_threshold and current_burst > self.burst_threshold:
            return self._evaluate_entry(
                current_signal, current_burst, curr_perp_px, curr_spot_px, curr_funding, bar_vol, bar_vol_usd
            )

        return None

    def _manage_active_position(
        self, curr_px: float, sig: float, burst: float, bar_vol: float, bar_vol_usd: float
    ) -> Optional[Dict[str, Any]]:
        """
        活跃持仓的动态管理逻辑（硬止损、追踪移动止盈、动量反转退出）。
        """
        if self.position_size_coin > 0:
            self.peak_price = max(self.peak_price, curr_px)
            dd_from_peak = (self.peak_price - curr_px) / self.entry_price
            loss_from_entry = (self.entry_price - curr_px) / self.entry_price
        else:
            self.peak_price = min(self.peak_price, curr_px)
            dd_from_peak = (curr_px - self.peak_price) / self.entry_price
            loss_from_entry = (curr_px - self.entry_price) / self.entry_price

        must_exit = False
        exit_reason = None

        if loss_from_entry >= self.stop_loss_pct:
            must_exit = True
            exit_reason = "硬止损触发 (HARD_STOP_LOSS)"
        elif dd_from_peak >= self.take_profit_trailing_pct and ((curr_px - self.entry_price) * np.sign(self.position_size_coin) > 0.015):
            must_exit = True
            exit_reason = "追踪移动止盈 (TRAILING_TAKE_PROFIT)"
        elif np.sign(sig) != np.sign(self.position_size_coin) and abs(sig) > 0.35:
            must_exit = True
            exit_reason = "微观动量反转 (MOMENTUM_REVERSAL)"
        elif burst < 0.20 and abs(sig) < 0.12:
            must_exit = True
            exit_reason = "情绪动能衰竭 (BURST_EXHAUSTION)"

        if must_exit:
            order_action = {
                'action': 'CLOSE',
                'channel': self.position_channel,
                'direction': 'SELL' if self.position_size_coin > 0 else 'BUY',
                'size_coin': abs(self.position_size_coin),
                'order_type': 'IOC_POV_SLICE',
                'reason': exit_reason
            }
            logger.info(f"触发平仓: {exit_reason}, 当前价格={curr_px:.6f}, 入场价={self.entry_price:.6f}")
            
            # 状态重置
            if loss_from_entry >= self.stop_loss_pct:
                self.consecutive_losses += 1
                if self.consecutive_losses >= 3:
                    self.is_cooling_down = True
                    self.cool_down_until = time.time() + 1800 # 30分钟冷却
                    logger.warning("连续触发 3 笔止损，进入 30 分钟保护性冷却期。")
            else:
                self.consecutive_losses = 0

            self.position_size_coin = 0.0
            self.position_channel = None
            self.entry_price = 0.0
            self.peak_price = 0.0
            return order_action

        return None

    def _evaluate_entry(
        self, sig: float, burst: float, perp_px: float, spot_px: float, funding: float, bar_vol: float, bar_vol_usd: float
    ) -> Dict[str, Any]:
        """
        开仓评估与跨通道路由。
        """
        direction = 1 if sig > 0 else -1
        
        # 跨通道智能路由: 正费率且大涨多头走现货，避免资金费率磨损；其余走永续
        if direction > 0 and funding > 0.0006:
            target_channel = 'spot'
            exec_px = spot_px
        else:
            target_channel = 'perp'
            exec_px = perp_px

        # 波动率自适应仓位与凯利分数
        leverage_target = min(self.max_leverage, (abs(sig) * self.max_leverage) * (0.02 / (bar_vol * np.sqrt(288) + 1e-4)))
        order_usd = min(self.capital_usd * leverage_target, self.initial_capital_usd * self.max_leverage)
        size_coin = (order_usd / exec_px) * direction

        # 更新持仓状态
        self.position_size_coin = size_coin
        self.position_channel = target_channel
        self.entry_price = exec_px
        self.peak_price = exec_px

        order_action = {
            'action': 'OPEN',
            'channel': target_channel,
            'direction': 'BUY' if direction > 0 else 'SELL',
            'size_coin': abs(size_coin),
            'order_type': 'IOC_POV_SLICE',
            'leverage': leverage_target,
            'signal_score': float(sig),
            'burst_confidence': float(burst)
        }
        logger.info(
            f"下发开仓指令: 通道={target_channel}, 方向={'多头' if direction > 0 else '空头'}, "
            f"规模={order_usd:,.2f} USD, 信号得分={sig:.3f}, 爆发置信度={burst:.3f}"
        )
        return order_action


if __name__ == '__main__':
    print("=" * 60)
    print("DOGE 高频非线性动量实盘运行器模块测试")
    print("=" * 60)
    trader = DogeMicrostructureStrategy()
    print("实盘交易系统就绪。")
