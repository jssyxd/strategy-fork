"""as_discrete_linear_engine.py - 工业级离散 A-S 线性库存控制与做市执行器

对齐聊天记录图 7、图 8 的一线量化工程落地：
将学术界连续时间、依赖未知参数的复杂 PDE 简化为极其实用的线性持仓比率偏移:
1. 平仓侧 (Exit/Close):
   shift_exit = 1.0 - (inventory / max_inventory) * 0.5
   持有多仓越重，卖平仓挂单越主动向定价中枢贴近，降低出清门槛，防止逆向暴跌穿仓。
2. 开仓侧 (Entry/Open):
   shift_entry = 1.0 + (inventory / max_inventory) * 2.0
   持有多仓越重，买开仓挂单越远离中枢（退避防御），坚决拒绝逆势补仓加仓。
3. 冲量门控 (Impulse Gate) - 融入图 9 消融结论:
   若市场出现瞬时急跌跌幅 >= 12 bp，判定为知情大单 (Toxic Flow)，瞬间撤销所有买入开仓挂单！
"""

import numpy as np
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ASGridConfig:
    symbol: str = "AG2612"            # 白银期货主力
    base_spread_bps: float = 4.0      # 基础半价差 (4 bps)
    max_inventory: int = 10           # 最大单向持仓手数
    shift_exit_factor: float = 0.5    # 平仓侧靠近系数
    shift_entry_factor: float = 2.0   # 开仓侧远离系数
    toxic_drop_threshold_bps: float = 12.0 # 冲量门控阈值 (12 bps)
    fee_per_hand: float = 2.5         # 每手交易所手续费
    tick_size: float = 1.0            # 白银跳价 1元/千克


class DiscreteLinearASGrid:
    """离散非对称 A-S 做市与均值回归引擎"""

    def __init__(self, config: Optional[ASGridConfig] = None):
        self.cfg = config or ASGridConfig()
        self.inventory = 0            # 当前持仓 (多为正，空为负)
        self.trade_logs = []
        self.pnl_history = [0.0]

    def compute_quote_orders(
        self,
        mid_price: float,
        instant_return_bps: float,
    ) -> Dict[str, Any]:
        """
        根据当前中间价与瞬时冲量计算买一卖一挂单价格与风控状态
        """
        # 1. 冲量门控检测 (防刺客)
        # 若瞬时急跌 >= 12 bp，买盘开仓全面冻结
        is_toxic_drop = bool(instant_return_bps <= -self.cfg.toxic_drop_threshold_bps)
        # 若瞬时急涨 >= 12 bp，卖盘开仓全面冻结
        is_toxic_surge = bool(instant_return_bps >= self.cfg.toxic_drop_threshold_bps)

        pos_ratio = self.inventory / float(self.cfg.max_inventory) # [-1.0, 1.0]

        # 2. 基础半价差绝对金额
        base_half_spread = mid_price * (self.cfg.base_spread_bps / 10000.0)

        # 3. 多仓状态 (pos_ratio > 0): 平仓侧迎上去，开仓侧躲开
        if pos_ratio >= 0:
            # 卖平多仓挂单: shift = 1 - pos_ratio * 0.5 (变近)
            ask_shift = max(0.1, 1.0 - pos_ratio * self.cfg.shift_exit_factor)
            # 买开多仓挂单: shift = 1 + pos_ratio * 2.0 (变远)
            bid_shift = 1.0 + pos_ratio * self.cfg.shift_entry_factor
        # 空仓状态 (pos_ratio < 0): 镜像对称
        else:
            abs_ratio = abs(pos_ratio)
            # 买平空仓挂单: 变近
            bid_shift = max(0.1, 1.0 - abs_ratio * self.cfg.shift_exit_factor)
            # 卖开空仓挂单: 变远
            ask_shift = 1.0 + abs_ratio * self.cfg.shift_entry_factor

        # 计算并按 Tick Size 取整挂单价
        bid_price = np.floor((mid_price - base_half_spread * bid_shift) / self.cfg.tick_size) * self.cfg.tick_size
        ask_price = np.ceil((mid_price + base_half_spread * ask_shift) / self.cfg.tick_size) * self.cfg.tick_size

        # 风控拦截开关
        allow_buy = not is_toxic_drop and (self.inventory < self.cfg.max_inventory)
        allow_sell = not is_toxic_surge and (self.inventory > -self.cfg.max_inventory)

        return {
            "mid_price": mid_price,
            "bid_price": bid_price if allow_buy else None,
            "ask_price": ask_price if allow_sell else None,
            "allow_buy": allow_buy,
            "allow_sell": allow_sell,
            "pos_ratio": pos_ratio,
            "is_toxic_flow": is_toxic_drop or is_toxic_surge,
        }

    def on_fill(self, fill_side: str, fill_price: float, fill_qty: int = 1) -> Dict[str, Any]:
        """记录成交更新库存与 PnL"""
        old_inv = self.inventory
        if fill_side == "BUY":
            self.inventory += fill_qty
        elif fill_side == "SELL":
            self.inventory -= fill_qty

        cost = self.cfg.fee_per_hand * fill_qty
        trade_event = {
            "side": fill_side,
            "price": fill_price,
            "qty": fill_qty,
            "old_inventory": old_inv,
            "new_inventory": self.inventory,
            "fee": cost,
        }
        self.trade_logs.append(trade_event)
        return trade_event
