#!/usr/bin/env python3
"""
Strict FIFO Inventory Accounting & Realized PnL Engine
Ensures high-frequency market making trades are matched against real inventory acquisition cost,
preventing the instantaneous half-spread accounting distortion.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np

@dataclass
class FIFORoundTripTrade:
    trade_id: int
    entry_time: str
    exit_time: str
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    exit_price: float
    gross_pnl: float
    fee_paid: float
    net_pnl: float
    is_win: bool
    holding_bars: int


class FIFOInventoryTracker:
    """
    Strict FIFO (First-In-First-Out) Inventory Matching Engine.
    Matches every closing fill against the earliest open inventory acquisition price.
    """

    def __init__(self, fee_per_hand: float = 2.5):
        self.fee_per_hand = fee_per_hand
        self.buy_queue: List[Dict[str, Any]] = []   # Queue of open long fills
        self.sell_queue: List[Dict[str, Any]] = []  # Queue of open short fills
        self.completed_trades: List[FIFORoundTripTrade] = []
        self.trade_counter = 0

    def record_fill(self, side: str, price: float, timestamp: Any, bar_idx: int) -> Optional[FIFORoundTripTrade]:
        """
        Records an execution fill and performs FIFO matching if closing existing inventory.
        """
        time_str = str(timestamp)
        round_trip: Optional[FIFORoundTripTrade] = None

        if side == "BUY":
            # If open short inventory exists, this buy closes a short
            if self.sell_queue:
                entry = self.sell_queue.pop(0)
                gross_pnl = entry["price"] - price  # Short profit = Entry - Exit
                fee = self.fee_per_hand * 2.0
                net_pnl = gross_pnl - fee
                self.trade_counter += 1
                round_trip = FIFORoundTripTrade(
                    trade_id=self.trade_counter,
                    entry_time=entry["time"],
                    exit_time=time_str,
                    direction="SHORT",
                    entry_price=round(entry["price"], 2),
                    exit_price=round(price, 2),
                    gross_pnl=round(gross_pnl, 2),
                    fee_paid=round(fee, 2),
                    net_pnl=round(net_pnl, 2),
                    is_win=net_pnl > 0,
                    holding_bars=bar_idx - entry["bar_idx"]
                )
                self.completed_trades.append(round_trip)
            else:
                # Open new long inventory
                self.buy_queue.append({"price": price, "time": time_str, "bar_idx": bar_idx})

        elif side == "SELL":
            # If open long inventory exists, this sell closes a long
            if self.buy_queue:
                entry = self.buy_queue.pop(0)
                gross_pnl = price - entry["price"]  # Long profit = Exit - Entry
                fee = self.fee_per_hand * 2.0
                net_pnl = gross_pnl - fee
                self.trade_counter += 1
                round_trip = FIFORoundTripTrade(
                    trade_id=self.trade_counter,
                    entry_time=entry["time"],
                    exit_time=time_str,
                    direction="LONG",
                    entry_price=round(entry["price"], 2),
                    exit_price=round(price, 2),
                    gross_pnl=round(gross_pnl, 2),
                    fee_paid=round(fee, 2),
                    net_pnl=round(net_pnl, 2),
                    is_win=net_pnl > 0,
                    holding_bars=bar_idx - entry["bar_idx"]
                )
                self.completed_trades.append(round_trip)
            else:
                # Open new short inventory
                self.sell_queue.append({"price": price, "time": time_str, "bar_idx": bar_idx})

        return round_trip

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Calculates strict round-trip performance metrics."""
        if not self.completed_trades:
            return {
                "round_trips_count": 0,
                "win_rate_pct": 0.0,
                "total_net_pnl": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0
            }

        pnls = [t.net_pnl for t in self.completed_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        
        n_trades = len(pnls)
        n_wins = len(wins)
        win_rate = (n_wins / n_trades * 100.0) if n_trades > 0 else 0.0
        total_net_pnl = float(sum(pnls))
        
        gross_profit = float(sum(wins)) if wins else 0.0
        gross_loss = abs(float(sum(losses))) if losses else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 999.0
        
        return {
            "round_trips_count": n_trades,
            "win_rate_pct": round(win_rate, 2),
            "winning_trades": n_wins,
            "losing_trades": len(losses),
            "total_net_pnl_rmb": round(total_net_pnl, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win_rmb": round(float(np.mean(wins)), 2) if wins else 0.0,
            "avg_loss_rmb": round(float(np.mean(losses)), 2) if losses else 0.0,
            "avg_pnl_per_trade_rmb": round(total_net_pnl / n_trades, 2)
        }
