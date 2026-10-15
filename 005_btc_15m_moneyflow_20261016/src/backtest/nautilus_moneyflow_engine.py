"""
NautilusTrader Event-Driven MoneyFlow Backtest Engine (100% Causal & Deterministic).
Features:
- Pure bar-by-bar discrete event processing.
- Micro-liquidity signals:
  - RULE_1_LONG_SWEEP_OFI_ABSORPTION: Liquidity sweep below 48-bar swing low with OFI absorption.
  - RULE_2_SHORT_SWEEP_OFI_ABSORPTION: Liquidity sweep above 48-bar swing high with OFI absorption.
- Pessimistic slippage: 5 bps (0.0005) on market entry, stop loss, and market time exits.
- Pessimistic collision handling: if both TP and SL are touched in the same bar, STOP LOSS is triggered first.
- Maker fee (0.02%) on TP limit orders, Taker fee (Binance 0.04%, OKX 0.05%) on market orders.
- Full trade auditing: entry_rule, exit_reason, hold_bars, timestamps, prices, and fees.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

@dataclass
class TradeRecord:
    entry_time: str
    exit_time: str
    symbol: str
    direction: str
    entry_rule: str
    entry_price: float
    exit_price: float
    quantity: float
    notional: float
    leverage: float
    cost: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    hold_bars: int

@dataclass
class BacktestConfig:
    symbol: str = "BTC"
    initial_capital: float = 10000.0
    leverage: float = 5.0
    exchange: str = "binance" # "binance" or "okx"
    maker_fee: float = 0.0002
    taker_fee: float = 0.0004
    slippage_bps: float = 0.0005 # 5 bps
    risk_pct: float = 0.01 # 1.0% equity risk per trade
    atr_sl_mult: float = 1.2
    atr_tp_mult: float = 2.2
    max_hold_bars: int = 16 # 4 hours
    cooldown_bars: int = 16 # minimum bars between exits and new entries
    start_date: Optional[str] = "2023-01-01"
    end_date: Optional[str] = "2025-12-31"

class NautilusMoneyFlowEngine:
    def __init__(self, config: BacktestConfig):
        self.cfg = config
        if self.cfg.exchange.lower() == "okx":
            self.cfg.taker_fee = 0.0005
            self.cfg.maker_fee = 0.0002
        else: # binance
            self.cfg.taker_fee = 0.0004
            self.cfg.maker_fee = 0.0002

    def run(self, df: pd.DataFrame, features: pd.DataFrame) -> Dict:
        # Align index
        common_idx = df.index.intersection(features.index)
        df = df.loc[common_idx]
        features = features.loc[common_idx]
        
        capital = self.cfg.initial_capital
        trades: List[TradeRecord] = []
        equity_curve: List[float] = [capital]
        timestamps: List[pd.Timestamp] = [df.index[0]]
        
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        times = df.index
        
        atr = features['atr14'].values
        ofi = features['ofi_impulse'].values
        cmf = features['cmf_16'].values
        vol_comp = features['vol_compression'].values
        
        # 48-bar (12 hour) Swing High & Low
        sw_high = pd.Series(highs).rolling(48).max().shift(1).values
        sw_low = pd.Series(lows).rolling(48).min().shift(1).values
        
        # Microstructure Rules
        # Rule 1: Long sweep absorption
        rule1_sig = (lows <= sw_low) & (closes > sw_low) & (ofi > -0.05) & (vol_comp < 1.15)
        # Rule 2: Short sweep absorption
        rule2_sig = (highs >= sw_high) & (closes < sw_high) & (ofi < 0.05) & (vol_comp < 1.15)
        
        pos_dir = 0 # 1: Long, -1: Short, 0: Flat
        pos_entry_price = 0.0
        pos_size = 0.0
        pos_entry_time = None
        pos_entry_bar = 0
        pos_entry_rule = ""
        pos_sl = 0.0
        pos_tp = 0.0
        last_exit_bar = -50
        
        n_bars = len(df)
        slip = self.cfg.slippage_bps
        
        for i in range(50, n_bars - 1):
            curr_time = times[i]
            c, o, h, l = closes[i], opens[i], highs[i], lows[i]
            curr_atr = atr[i] if not np.isnan(atr[i]) else c * 0.015
            
            # 1. Manage Open Position
            if pos_dir != 0:
                hold_len = i - pos_entry_bar
                exit_price = None
                exit_reason = None
                is_maker = False
                
                if pos_dir == 1: # LONG
                    hit_sl = l <= pos_sl
                    hit_tp = h >= pos_tp
                    
                    if hit_sl and hit_tp:
                        # Pessimistic collision rule: assume Stop Loss hit first
                        exit_price = pos_sl * (1.0 - slip)
                        exit_reason = "SL_PESSIMISTIC_COLLISION"
                    elif hit_sl:
                        exit_price = min(o, pos_sl) * (1.0 - slip)
                        exit_reason = "SL_STOP_HIT"
                    elif hit_tp:
                        exit_price = pos_tp # Limit order fill
                        exit_reason = "TP_LIMIT_HIT"
                        is_maker = True
                    elif hold_len >= self.cfg.max_hold_bars:
                        exit_price = c * (1.0 - slip)
                        exit_reason = "TIME_EXIT_4H"
                        
                    if exit_price is not None:
                        gross_pnl = pos_size * (exit_price - pos_entry_price)
                        entry_fee = (pos_size * pos_entry_price) * self.cfg.taker_fee
                        exit_fee = (pos_size * exit_price) * (self.cfg.maker_fee if is_maker else self.cfg.taker_fee)
                        total_fee = entry_fee + exit_fee
                        net_pnl = gross_pnl - total_fee
                        
                        capital += net_pnl
                        trades.append(TradeRecord(
                            entry_time=str(pos_entry_time),
                            exit_time=str(curr_time),
                            symbol=self.cfg.symbol,
                            direction="LONG",
                            entry_rule=pos_entry_rule,
                            entry_price=round(pos_entry_price, 2),
                            exit_price=round(exit_price, 2),
                            quantity=round(pos_size, 4),
                            notional=round(pos_size * pos_entry_price, 2),
                            leverage=self.cfg.leverage,
                            cost=round(total_fee, 2),
                            pnl=round(net_pnl, 2),
                            pnl_pct=round(net_pnl / (capital - net_pnl + 1e-6), 4),
                            exit_reason=exit_reason,
                            hold_bars=hold_len
                        ))
                        pos_dir = 0
                        last_exit_bar = i
                        
                elif pos_dir == -1: # SHORT
                    hit_sl = h >= pos_sl
                    hit_tp = l <= pos_tp
                    
                    if hit_sl and hit_tp:
                        exit_price = pos_sl * (1.0 + slip)
                        exit_reason = "SL_PESSIMISTIC_COLLISION"
                    elif hit_sl:
                        exit_price = max(o, pos_sl) * (1.0 + slip)
                        exit_reason = "SL_STOP_HIT"
                    elif hit_tp:
                        exit_price = pos_tp
                        exit_reason = "TP_LIMIT_HIT"
                        is_maker = True
                    elif hold_len >= self.cfg.max_hold_bars:
                        exit_price = c * (1.0 + slip)
                        exit_reason = "TIME_EXIT_4H"
                        
                    if exit_price is not None:
                        gross_pnl = pos_size * (pos_entry_price - exit_price)
                        entry_fee = (pos_size * pos_entry_price) * self.cfg.taker_fee
                        exit_fee = (pos_size * exit_price) * (self.cfg.maker_fee if is_maker else self.cfg.taker_fee)
                        total_fee = entry_fee + exit_fee
                        net_pnl = gross_pnl - total_fee
                        
                        capital += net_pnl
                        trades.append(TradeRecord(
                            entry_time=str(pos_entry_time),
                            exit_time=str(curr_time),
                            symbol=self.cfg.symbol,
                            direction="SHORT",
                            entry_rule=pos_entry_rule,
                            entry_price=round(pos_entry_price, 2),
                            exit_price=round(exit_price, 2),
                            quantity=round(pos_size, 4),
                            notional=round(pos_size * pos_entry_price, 2),
                            leverage=self.cfg.leverage,
                            cost=round(total_fee, 2),
                            pnl=round(net_pnl, 2),
                            pnl_pct=round(net_pnl / (capital - net_pnl + 1e-6), 4),
                            exit_reason=exit_reason,
                            hold_bars=hold_len
                        ))
                        pos_dir = 0
                        last_exit_bar = i
                        
            # 2. Check New Entry if Flat and Cooldown satisfied
            if pos_dir == 0 and capital > 10.0 and (i - last_exit_bar >= self.cfg.cooldown_bars):
                l_sig = rule1_sig[i]
                s_sig = rule2_sig[i]
                
                if l_sig or s_sig:
                    next_open = opens[i+1]
                    sl_dist = curr_atr * self.cfg.atr_sl_mult
                    risk_amount = capital * self.cfg.risk_pct
                    desired_size = risk_amount / (sl_dist + 1e-6)
                    max_allowed_size = (capital * self.cfg.leverage) / next_open
                    size = min(desired_size, max_allowed_size)
                    
                    if l_sig and size > 0:
                        pos_dir = 1
                        pos_entry_price = next_open * (1.0 + slip)
                        pos_size = size
                        pos_entry_time = times[i+1]
                        pos_entry_bar = i + 1
                        pos_entry_rule = "RULE_1_LONG_SWEEP_OFI_ABSORPTION"
                        pos_sl = pos_entry_price - sl_dist
                        pos_tp = pos_entry_price + curr_atr * self.cfg.atr_tp_mult
                    elif s_sig and size > 0:
                        pos_dir = -1
                        pos_entry_price = next_open * (1.0 - slip)
                        pos_size = size
                        pos_entry_time = times[i+1]
                        pos_entry_bar = i + 1
                        pos_entry_rule = "RULE_2_SHORT_SWEEP_OFI_ABSORPTION"
                        pos_sl = pos_entry_price + sl_dist
                        pos_tp = pos_entry_price - curr_atr * self.cfg.atr_tp_mult
                        
            equity_curve.append(capital)
            timestamps.append(curr_time)
            
        eq_series = pd.Series(equity_curve, index=timestamps)
        total_ret = (capital - self.cfg.initial_capital) / self.cfg.initial_capital
        rolling_max = eq_series.cummax()
        dd = (eq_series - rolling_max) / rolling_max
        max_dd = abs(dd.min())
        
        n_trades = len(trades)
        wins = [t for t in trades if t.pnl > 0]
        win_rate = len(wins) / n_trades if n_trades > 0 else 0.0
        
        daily_eq = eq_series.resample('1D').last().ffill().dropna()
        daily_ret = daily_eq.pct_change().dropna()
        sharpe = (daily_ret.mean() / (daily_ret.std() + 1e-6)) * np.sqrt(365) if len(daily_ret) > 1 else 0.0
        
        duration_years = (times[-1] - times[0]).days / 365.25
        cagr = (capital / self.cfg.initial_capital) ** (1.0 / max(duration_years, 0.1)) - 1.0 if (duration_years > 0 and capital > 0) else 0.0
        calmar = cagr / (max_dd + 1e-6)
        
        tp_count = len([t for t in trades if t.exit_reason == "TP_LIMIT_HIT"])
        sl_count = len([t for t in trades if "SL" in t.exit_reason])
        time_count = len([t for t in trades if t.exit_reason == "TIME_EXIT_4H"])
        
        return {
            "symbol": self.cfg.symbol,
            "exchange": self.cfg.exchange,
            "leverage": self.cfg.leverage,
            "initial_capital": self.cfg.initial_capital,
            "final_equity": round(capital, 2),
            "total_return_pct": round(total_ret * 100, 2),
            "cagr_pct": round(cagr * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "calmar_ratio": round(calmar, 2),
            "total_trades": n_trades,
            "win_rate_pct": round(win_rate * 100, 2),
            "tp_count": tp_count,
            "sl_count": sl_count,
            "time_count": time_count,
            "trades": trades,
            "equity_curve": eq_series
        }
