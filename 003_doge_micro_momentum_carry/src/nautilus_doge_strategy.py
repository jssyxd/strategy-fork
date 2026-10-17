"""
Jane Street Grade Nautilus Trader Strategy Implementation:
DOGE High-Frequency Microstructure Nonlinear Momentum Strategy (008_doge_momentum).
Ported to pure Nautilus Trader native event-driven Architecture.
"""

from collections import deque
import numpy as np
from decimal import Decimal

from nautilus_trader.trading import Strategy, StrategyConfig
from nautilus_trader.model import (
    Bar, BarType, InstrumentId, OrderSide, Quantity, Price, TimeInForce
)

class DogeMomentumConfig(StrategyConfig):
    """
    Configuration parameters for DOGE Momentum Strategy in Nautilus Trader.
    """
    def __init__(
        self,
        instrument_id: InstrumentId,
        bar_type: BarType,
        fast_ema_period: int = 12,
        slow_ema_period: int = 48,
        cvd_window: int = 36,
        vol_surge_window: int = 24,
        leverage: float = 2.0,
        stop_loss_pct: float = 0.020,
        trailing_tp_pct: float = 0.035,
        min_tp_activation_pct: float = 0.015,
        trade_size_doge: float = 2000000.0, # Scaled position unit
    ):
        super().__init__()
        self.instrument_id = instrument_id
        self.bar_type = bar_type
        self.fast_ema_period = fast_ema_period
        self.slow_ema_period = slow_ema_period
        self.cvd_window = cvd_window
        self.vol_surge_window = vol_surge_window
        self.leverage = leverage
        self.stop_loss_pct = stop_loss_pct
        self.trailing_tp_pct = trailing_tp_pct
        self.min_tp_activation_pct = min_tp_activation_pct
        self.trade_size_doge = trade_size_doge


class NautilusDogeMomentumStrategy(Strategy):
    """
    Nautilus Trader native event-driven Strategy for DOGE Momentum.
    Executes:
    1. Trend Gating (Dual EMA).
    2. CVD / Microstructure Volume Divergence.
    3. Volume Surge Filter.
    4. Dynamic Position Risk Management (Trailing TP, Hard Stop, Trend Reversal Exit).
    """
    def __init__(self, config: DogeMomentumConfig):
        super().__init__(config)
        self.cfg = config
        self.instrument_id = config.instrument_id
        self.bar_type = config.bar_type

        # Time series buffers for factor calculation
        self.close_prices = deque(maxlen=config.slow_ema_period + 20)
        self.volumes = deque(maxlen=config.vol_surge_window + 20)
        self.cvd_history = deque(maxlen=config.cvd_window + 20)
        self.cumulative_volume_delta = 0.0
        
        # Position tracking state
        self.entry_price = 0.0
        self.peak_price = 0.0
        self.bars_in_trade = 0
        self.trade_count = 0
        self.realized_pnl_tracker = 0.0

    def on_start(self):
        self.log.info(f"Starting NautilusDogeMomentumStrategy on {self.instrument_id}")
        self.subscribe_bars(self.bar_type)

    def on_bar(self, bar: Bar):
        px = float(bar.close)
        vol = float(bar.volume)
        
        # 1. Update rolling price & volume buffers
        self.close_prices.append(px)
        self.volumes.append(vol)

        # Microstructure proxy: price change direction * volume
        if len(self.close_prices) > 1:
            delta_p = px - self.close_prices[-2]
            delta_v = vol if delta_p > 0 else (-vol if delta_p < 0 else 0.0)
        else:
            delta_v = 0.0
            
        self.cumulative_volume_delta += delta_v
        self.cvd_history.append(self.cumulative_volume_delta)

        # Ensure warm-up period is met
        if len(self.close_prices) < self.cfg.slow_ema_period:
            return

        # 2. Factor 1: Macro Dual Trend EMA
        close_arr = np.array(self.close_prices)
        alpha_fast = 2.0 / (self.cfg.fast_ema_period + 1.0)
        alpha_slow = 2.0 / (self.cfg.slow_ema_period + 1.0)
        
        ema_f = close_arr[0]
        for c in close_arr[1:]:
            ema_f = alpha_fast * c + (1.0 - alpha_fast) * ema_f
            
        ema_s = close_arr[0]
        for c in close_arr[1:]:
            ema_s = alpha_slow * c + (1.0 - alpha_slow) * ema_s
            
        trend_direction = 1 if ema_f > ema_s else -1

        # 3. Factor 2: CVD Z-Score & Divergence
        if len(self.cvd_history) >= self.cfg.cvd_window:
            cvd_slice = np.array(list(self.cvd_history)[-self.cfg.cvd_window:])
            px_slice = close_arr[-self.cfg.cvd_window:]
            
            std_cvd = np.std(cvd_slice) + 1e-8
            std_px = np.std(px_slice) + 1e-8
            
            z_cvd = (cvd_slice[-1] - np.mean(cvd_slice)) / std_cvd
            z_px = (px_slice[-1] - np.mean(px_slice)) / std_px
            cvd_divergence = z_cvd - z_px
        else:
            cvd_divergence = 0.0

        # 4. Factor 3: Volume Surge
        if len(self.volumes) >= self.cfg.vol_surge_window:
            vol_mean = np.mean(list(self.volumes)[-self.cfg.vol_surge_window:]) + 1e-8
            vol_surge = vol / vol_mean
        else:
            vol_surge = 1.0

        # 5. Position Management
        net_pos = float(self.portfolio.net_position(self.instrument_id))
        
        if net_pos != 0:
            self.bars_in_trade += 1
            if net_pos > 0:
                self.peak_price = max(self.peak_price, px)
                drawdown_from_peak = (self.peak_price - px) / self.entry_price
                loss_from_entry = (self.entry_price - px) / self.entry_price
            else:
                self.peak_price = min(self.peak_price, px)
                drawdown_from_peak = (px - self.peak_price) / self.entry_price
                loss_from_entry = (px - self.entry_price) / self.entry_price

            must_exit = False
            exit_reason = None

            # Hard stop
            if loss_from_entry >= self.cfg.stop_loss_pct:
                must_exit = True
                exit_reason = "HARD_STOP_LOSS"
            # Trailing take profit
            elif drawdown_from_peak >= self.cfg.trailing_tp_pct and ((px - self.entry_price) * np.sign(net_pos) > self.cfg.min_tp_activation_pct):
                must_exit = True
                exit_reason = "TRAILING_TAKE_PROFIT"
            # Trend reversal
            elif np.sign(trend_direction) != np.sign(net_pos):
                must_exit = True
                exit_reason = "TREND_REVERSAL_EXIT"

            if must_exit:
                self.log.info(f"Exiting position: reason={exit_reason}, px={px:.5f}, entry={self.entry_price:.5f}, peak={self.peak_price:.5f}")
                self.close_all_positions(self.instrument_id)
                self.entry_price = 0.0
                self.peak_price = 0.0
                self.bars_in_trade = 0
                return

        # 6. Signal Evaluation & Entry Execution
        if net_pos == 0:
            # Long entry
            if trend_direction > 0 and cvd_divergence > 1.0 and vol_surge > 1.25:
                trade_qty = Quantity.from_str(str(round(self.cfg.trade_size_doge, 1)))
                order = self.order_factory.market(
                    instrument_id=self.instrument_id,
                    order_side=OrderSide.BUY,
                    quantity=trade_qty
                )
                self.submit_order(order)
                self.entry_price = px
                self.peak_price = px
                self.bars_in_trade = 0
                self.trade_count += 1
                self.log.info(f"Signal LONG entered: px={px:.5f}, cvd_div={cvd_divergence:.2f}, vol_surge={vol_surge:.2f}")

            # Short entry
            elif trend_direction < 0 and cvd_divergence < -1.0 and vol_surge > 1.25:
                trade_qty = Quantity.from_str(str(round(self.cfg.trade_size_doge, 1)))
                order = self.order_factory.market(
                    instrument_id=self.instrument_id,
                    order_side=OrderSide.SELL,
                    quantity=trade_qty
                )
                self.submit_order(order)
                self.entry_price = px
                self.peak_price = px
                self.bars_in_trade = 0
                self.trade_count += 1
                self.log.info(f"Signal SHORT entered: px={px:.5f}, cvd_div={cvd_divergence:.2f}, vol_surge={vol_surge:.2f}")

    def on_stop(self):
        self.log.info(f"NautilusDogeMomentumStrategy stopped. Total trades executed: {self.trade_count}")
