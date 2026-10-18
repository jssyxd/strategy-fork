"""
NautilusTrader IntraBar Recalculation Strategy for 002 Matrix.
Executes Macro Bar signals with Micro 1-Minute intra-bar order execution and recalculation.
Strictly causal: macro indicators calculated on bar i-1 are applied to bar i micro slices.
"""

from nautilus_trader.trading import Strategy, StrategyConfig
from decimal import Decimal
import numpy as np
import pandas as pd
from nautilus_trader.model import (
    InstrumentId, Venue, OrderSide, TimeInForce, BarType, Bar, Price, Quantity, Currency
)


class NautilusIntraBarMatrixConfig(StrategyConfig):
    def __init__(
        self,
        instrument_id: InstrumentId,
        macro_bar_type: BarType,
        micro_bar_type: BarType,
        limit_pullback_pct: float = 0.002,
        atr_sl_mult: float = 1.2,
        atr_tp_mult: float = 2.4,
        risk_per_trade: float = 0.01,
        max_leverage: float = 3.0,
        max_hold_macro_bars: int = 12,
    ):
        super().__init__()
        self.instrument_id = instrument_id
        self.macro_bar_type = macro_bar_type
        self.micro_bar_type = micro_bar_type
        self.limit_pullback_pct = limit_pullback_pct
        self.atr_sl_mult = atr_sl_mult
        self.atr_tp_mult = atr_tp_mult
        self.risk_per_trade = risk_per_trade
        self.max_leverage = max_leverage
        self.max_hold_macro_bars = max_hold_macro_bars


class NautilusIntraBarMatrixStrategy(Strategy):
    """
    True Causal NautilusTrader Event-Driven Matrix Strategy:
    1. Subscribes to macro bars (e.g. 15m, 1h, 3h) to update regime (EMA20 > EMA50) and ATR(14)
       strictly on completed macro bars.
    2. Subscribes to micro 1m bars to manage intra-bar execution:
       - Places/evaluates limit buy order when bullish regime is active.
       - Recalculates SL/TP immediately upon execution.
       - Manages exits at 1m resolution (TP/SL/Time-stop).
    """
    def __init__(self, config: NautilusIntraBarMatrixConfig):
        super().__init__(config)
        self.macro_bar_type = config.macro_bar_type
        self.micro_bar_type = config.micro_bar_type
        self.inst_id = config.instrument_id
        
        self.macro_closes = []
        self.macro_highs = []
        self.macro_lows = []
        
        self.current_regime_bull = False
        self.current_atr = 0.0
        self.prior_macro_close = 0.0
        self.macro_bar_count = 0
        
        # Position tracking
        self.active_pos = None # {entry_px, qty, sl_px, tp_px, entry_macro_idx}
        self.pending_limit_buy = None
        self.last_macro_traded = -1
        
        self.executed_trades = []

    def on_start(self):
        self.subscribe_bars(self.macro_bar_type)
        self.subscribe_bars(self.micro_bar_type)

    def on_bar(self, bar: Bar):
        # Dispatch based on bar type
        if bar.bar_type == self.macro_bar_type:
            self._handle_macro_bar(bar)
        elif bar.bar_type == self.micro_bar_type:
            self._handle_micro_bar(bar)

    def _handle_macro_bar(self, bar: Bar):
        """Called when a macro bar CLOSES."""
        self.macro_bar_count += 1
        c = float(bar.close)
        h = float(bar.high)
        l = float(bar.low)
        
        self.macro_closes.append(c)
        self.macro_highs.append(h)
        self.macro_lows.append(l)
        self.prior_macro_close = c
        
        # Need at least 50 bars for EMA50
        if len(self.macro_closes) >= 50:
            s_close = pd.Series(self.macro_closes)
            ema20 = s_close.ewm(span=20).mean().iloc[-1]
            ema50 = s_close.ewm(span=50).mean().iloc[-1]
            self.current_regime_bull = bool(ema20 > ema50)
            
            # ATR(14)
            s_high = pd.Series(self.macro_highs)
            s_low = pd.Series(self.macro_lows)
            prev_c = s_close.shift(1)
            tr = np.maximum(s_high - s_low, np.maximum((s_high - prev_c).abs(), (s_low - prev_c).abs()))
            self.current_atr = float(tr.rolling(14).mean().iloc[-1])
        else:
            self.current_regime_bull = False
            self.current_atr = c * 0.01

        # Setup pending limit buy for the UPCOMING interval
        if self.active_pos is None and self.current_regime_bull and self.last_macro_traded != self.macro_bar_count:
            self.pending_limit_buy = self.prior_macro_close * (1.0 - self.config.limit_pullback_pct)
        else:
            self.pending_limit_buy = None

    def _handle_micro_bar(self, bar: Bar):
        """Called every 1 minute."""
        low = float(bar.low)
        high = float(bar.high)
        close = float(bar.close)
        
        # 1. Check entry if flat and pending limit buy exists
        if self.active_pos is None and self.pending_limit_buy is not None:
            if low <= self.pending_limit_buy:
                # Filled!
                entry_px = min(self.pending_limit_buy, float(bar.open))
                # Slippage 3 bps
                entry_px *= (1.0 + 0.0003)
                
                # Sizing
                sl_dist = self.current_atr * self.config.atr_sl_mult
                equity = 100000.0
                risk_amt = equity * self.config.risk_per_trade
                desired_qty = risk_amt / max(sl_dist, 1e-6)
                max_qty = (equity * self.config.max_leverage) / entry_px
                qty = min(desired_qty, max_qty)
                
                # Recalculate SL and TP
                sl_px = entry_px - sl_dist
                tp_px = entry_px + (self.current_atr * self.config.atr_tp_mult)
                
                self.active_pos = {
                    'entry_px': entry_px,
                    'qty': qty,
                    'sl_px': sl_px,
                    'tp_px': tp_px,
                    'entry_bar_macro': self.macro_bar_count,
                    'entry_ts': bar.ts_event,
                }
                self.pending_limit_buy = None
                self.last_macro_traded = self.macro_bar_count
                return

        # 2. Check exits if in position
        if self.active_pos is not None:
            pos = self.active_pos
            sl_hit = low <= pos['sl_px']
            tp_hit = high >= pos['tp_px']
            time_hit = (self.macro_bar_count - pos['entry_bar_macro']) >= self.config.max_hold_macro_bars
            
            exit_trade = False
            exit_px = 0.0
            reason = ""
            
            if sl_hit and tp_hit:
                # Pessimistic collision
                exit_px = pos['sl_px'] * (1.0 - 0.0003)
                reason = "COLLISION_STOP_LOSS"
                exit_trade = True
            elif sl_hit:
                exit_px = pos['sl_px'] * (1.0 - 0.0003)
                reason = "STOP_LOSS"
                exit_trade = True
            elif tp_hit:
                exit_px = pos['tp_px'] * (1.0 - 0.0003)
                reason = "TAKE_PROFIT"
                exit_trade = True
            elif time_hit:
                exit_px = close * (1.0 - 0.0003)
                reason = "TIME_STOP"
                exit_trade = True
                
            if exit_trade:
                pnl = (exit_px - pos['entry_px']) * pos['qty'] - (exit_px + pos['entry_px']) * pos['qty'] * 0.0003
                self.executed_trades.append({
                    'entry_px': pos['entry_px'],
                    'exit_px': exit_px,
                    'qty': pos['qty'],
                    'pnl': pnl,
                    'reason': reason,
                    'bars_held': self.macro_bar_count - pos['entry_bar_macro']
                })
                self.active_pos = None
