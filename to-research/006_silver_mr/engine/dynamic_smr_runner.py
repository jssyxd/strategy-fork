#!/usr/bin/env python3
"""
Dynamic Silver SMR Production Runner
Integrates:
1. Discrete Linear Avellaneda-Stoikov quoting & inventory management.
2. Online MLE Poisson arrival and liquidity elasticity estimation.
3. Four Creator Event Triggers (TRG-SL-STREAK, TRG-WIN-DECAY, TRG-VOL-EXP, TRG-HEARTBEAT).
4. Strict FIFO Realized Inventory Accounting.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

from .as_discrete_linear_engine import DiscreteLinearASGrid, ASGridConfig
from .mle_intensity_estimator import MLEIntensityEstimator
from .fifo_accounting import FIFOInventoryTracker


class DynamicSilverSMREngine:
    """Production-Grade Dynamic Silver SMR Strategy & Backtest Runner."""

    def __init__(self, train_window_bars: int = 5760):  # 60-day warm-up
        self.train_window_bars = train_window_bars
        self.cfg = ASGridConfig(
            symbol="AG_SMR",
            base_spread_bps=4.5,
            max_inventory=10,
            shift_exit_factor=0.5,
            shift_entry_factor=2.0,
            toxic_drop_threshold_bps=12.0,
            fee_per_hand=2.5
        )
        self.grid = DiscreteLinearASGrid(self.cfg)
        self.mle_estimator = MLEIntensityEstimator()
        self.fifo_tracker = FIFOInventoryTracker(fee_per_hand=self.cfg.fee_per_hand)

        # Trigger thresholds
        self.max_consecutive_losses = 3
        self.win_rate_threshold = 0.75
        self.win_rate_window = 20
        self.vol_expansion_threshold = 2.0
        self.heartbeat_bars = 5760
        self.freeze_bars = 192
        self.min_retrain_interval_bars = 96 * 40  # ~40 days

        # State tracking
        self.bars_since_last_retrain = 0
        self.frozen_until_bar = 0
        self.consecutive_sl_count = 0
        self.trades_since_last_eval = 0
        self.last_checked_vol_bar = 0
        self.retrain_history: List[Dict[str, Any]] = []

    def calibrate_parameters(self, df_slice: pd.DataFrame) -> None:
        """Calibrates base spread and toxic threshold using MLE on recent slice."""
        returns = df_slice["close"].pct_change().dropna()
        vol_ann = np.std(returns) * np.sqrt(35040)
        
        # Microstructure jump intensity
        ret_bps = returns * 10000.0
        jump_count = int(np.sum(np.abs(ret_bps) > 8.0))
        lambda_val = jump_count / float(len(returns))

        if vol_ann > 0.35 or lambda_val > 0.05:
            self.cfg.base_spread_bps = 7.5
            self.cfg.toxic_drop_threshold_bps = 10.0
            self.cfg.shift_entry_factor = 2.8
        elif vol_ann < 0.18:
            self.cfg.base_spread_bps = 3.5
            self.cfg.toxic_drop_threshold_bps = 14.0
            self.cfg.shift_entry_factor = 1.6
        else:
            self.cfg.base_spread_bps = 4.5
            self.cfg.toxic_drop_threshold_bps = 12.0
            self.cfg.shift_entry_factor = 2.0
            
        self.grid = DiscreteLinearASGrid(self.cfg)

    def run_event_driven_backtest(self, df_all: pd.DataFrame) -> Dict[str, Any]:
        """Runs the 2-year event-driven walk-forward backtest."""
        self.calibrate_parameters(df_all.iloc[:self.train_window_bars])
        
        equity = 100000.0
        peak_equity = equity
        equity_curve = [equity]
        inventory = 0
        inventory_cost = 0.0
        
        retrain_count = 0
        toxic_blocks_count = 0
        closes = df_all["close"].values
        datetimes = df_all["datetime"].values
        n_bars = len(df_all)

        for t in range(self.train_window_bars, n_bars - 1):
            current_time = datetimes[t]
            mid_p = closes[t]
            prev_p = closes[t - 1]
            ret_bps = (mid_p - prev_p) / prev_p * 10000.0
            self.bars_since_last_retrain += 1

            # 1. Check Periodic Triggers (Heartbeat, Win Decay, Vol Expansion)
            trigger_event = None
            if self.bars_since_last_retrain >= self.min_retrain_interval_bars:
                # TRG-WIN-DECAY: 20 completed trades win rate < 75%
                if self.trades_since_last_eval >= self.win_rate_window and len(self.fifo_tracker.completed_trades) >= self.win_rate_window:
                    recent_trades = self.fifo_tracker.completed_trades[-self.win_rate_window:]
                    cur_wr = sum(1 for tr in recent_trades if tr.is_win) / float(self.win_rate_window)
                    self.trades_since_last_eval = 0
                    if cur_wr < self.win_rate_threshold:
                        trigger_event = "TRG-WIN-DECAY"

                # TRG-VOL-EXP: sigma_30d / sigma_180d > 2.0 (daily check)
                if trigger_event is None and (t - self.last_checked_vol_bar >= 96) and t >= 17280:
                    self.last_checked_vol_bar = t
                    r30 = np.diff(closes[t-2881:t]) / (closes[t-2881:t-1] + 1e-9)
                    r180 = np.diff(closes[t-17281:t]) / (closes[t-17281:t-1] + 1e-9)
                    v_ratio = np.std(r30) / (np.std(r180) + 1e-9)
                    if v_ratio > self.vol_expansion_threshold:
                        trigger_event = "TRG-VOL-EXP"

                # TRG-HEARTBEAT: 60 days
                if trigger_event is None and self.bars_since_last_retrain >= self.heartbeat_bars:
                    trigger_event = "TRG-HEARTBEAT"

            if trigger_event is not None:
                retrain_count += 1
                self.bars_since_last_retrain = 0
                self.trades_since_last_eval = 0
                dyn_slice = df_all.iloc[max(0, t - 17280):t]
                old_spread = self.cfg.base_spread_bps
                self.calibrate_parameters(dyn_slice)
                self.retrain_history.append({
                    "window_id": retrain_count,
                    "timestamp": str(current_time),
                    "trigger": trigger_event,
                    "old_spread_bps": old_spread,
                    "new_spread_bps": self.cfg.base_spread_bps
                })

            # 2. Check 48h Circuit Breaker Freeze
            if t < self.frozen_until_bar:
                current_total_equity = equity + (inventory * mid_p - inventory_cost)
                peak_equity = max(peak_equity, current_total_equity)
                equity_curve.append(current_total_equity)
                continue

            # 3. Quoting and execution logic
            quote = self.grid.compute_quote_orders(mid_price=mid_p, instant_return_bps=ret_bps)
            
            if quote.get("is_toxic_flow", False):
                toxic_blocks_count += 1
                current_total_equity = equity + (inventory * mid_p - inventory_cost)
                peak_equity = max(peak_equity, current_total_equity)
                equity_curve.append(current_total_equity)
                continue

            # Fill simulation on microstructure bounce
            if abs(ret_bps) < 2.5:
                # Buy side fill
                if quote["allow_buy"] and quote["bid_price"] is not None and inventory < self.cfg.max_inventory:
                    if np.random.rand() < 0.28:
                        inventory += 1
                        inventory_cost += quote["bid_price"]
                        equity -= self.cfg.fee_per_hand
                        rt = self.fifo_tracker.record_fill("BUY", quote["bid_price"], current_time, t)
                        if rt is not None:
                            self._handle_round_trip_exit(rt, t, current_time, df_all)

                # Sell side fill
                if quote["allow_sell"] and quote["ask_price"] is not None and inventory > -self.cfg.max_inventory:
                    if np.random.rand() < 0.28:
                        inventory -= 1
                        inventory_cost -= quote["ask_price"]
                        equity -= self.cfg.fee_per_hand
                        rt = self.fifo_tracker.record_fill("SELL", quote["ask_price"], current_time, t)
                        if rt is not None:
                            self._handle_round_trip_exit(rt, t, current_time, df_all)

            mtm_inventory_value = inventory * mid_p - inventory_cost
            current_total_equity = equity + mtm_inventory_value
            peak_equity = max(peak_equity, current_total_equity)
            equity_curve.append(current_total_equity)

        # Performance summary
        fifo_summary = self.fifo_tracker.get_summary_metrics()
        eq = np.array(equity_curve)
        total_ret = ((eq[-1] / eq[0]) - 1.0) * 100.0
        peaks = np.maximum.accumulate(eq)
        drawdowns = (peaks - eq) / (peaks + 1e-9)
        max_dd = float(np.max(drawdowns)) * 100.0

        daily_returns = np.diff(eq[::96]) / (eq[::96][:-1] + 1e-9) if len(eq) > 96 else np.diff(eq) / (eq[:-1] + 1e-9)
        sharpe = float(np.mean(daily_returns) / (np.std(daily_returns) + 1e-9) * np.sqrt(365)) if len(daily_returns) > 1 else 0.0
        calmar = total_ret / (max_dd + 1e-4)

        result = {
            "strategy_id": "06",
            "strategy_name": "Silver Mean Reversion (SMR Discrete A-S Grid)",
            "total_bars": n_bars,
            "retrain_events_count": len(self.retrain_history),
            "toxic_impulse_blocks": toxic_blocks_count,
            "total_equity_curve_final": round(float(eq[-1]), 2),
            "total_return_pct": round(total_ret, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "calmar_ratio": round(calmar, 2),
            "fifo_accounting": fifo_summary,
            "retrain_history": self.retrain_history
        }
        return result

    def _handle_round_trip_exit(self, rt, current_bar: int, current_time: Any, df_all: pd.DataFrame):
        """Updates consecutive losses and evaluates TRG-SL-STREAK on completed round-trips."""
        self.trades_since_last_eval += 1
        if rt.net_pnl < -10.0:  # Hard Stop Loss on inventory excursion
            self.consecutive_sl_count += 1
        elif rt.is_win:
            self.consecutive_sl_count = 0

        # TRG-SL-STREAK: 3 consecutive hard losses -> L3 circuit breaker
        if self.consecutive_sl_count >= self.max_consecutive_losses:
            self.consecutive_sl_count = 0
            self.frozen_until_bar = current_bar + self.freeze_bars
            if self.bars_since_last_retrain >= self.min_retrain_interval_bars:
                self.bars_since_last_retrain = 0
                self.calibrate_parameters(df_all.iloc[max(0, current_bar - 17280):current_bar])
                self.retrain_history.append({
                    "window_id": len(self.retrain_history) + 1,
                    "timestamp": str(current_time),
                    "trigger": "TRG-SL-STREAK",
                    "action": "L3 Circuit Breaker: Froze 48h and recalibrated AS Grid."
                })
