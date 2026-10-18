"""
Native NautilusTrader Event-Driven Backtest Runner for IntraBar Matrix Strategy.
Validates true execution inside NautilusTrader discrete-event engine using governed W:/database data.
"""

import sys
import os
import time
from decimal import Decimal
import pandas as pd
import numpy as np

from nautilus_trader.trading import StrategyConfig
from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.model import (
    Currency, Price, Quantity, Venue, InstrumentId, Symbol, TraderId,
    CurrencyPair, BarType, Bar, Money, OrderSide, TimeInForce, OmsType, AccountType
)
from nautilus_trader.execution import MakerTakerFeeModel

from multi_asset_loader import load_asset_1m_data, aggregate_timeframe_bars
from nautilus_causal_intrabar import NautilusIntraBarMatrixStrategy, NautilusIntraBarMatrixConfig


def run_nautilus_native_backtest(
    symbol_str="BTC",
    macro_tf="3h",
    initial_capital=100000.0,
):
    print("=" * 85)
    print(f" NAUTILUS TRADER OFFICIAL EVENT ENGINE - {symbol_str} ({macro_tf}) CAUSAL BACKTEST")
    print("=" * 85)

    engine_config = BacktestEngineConfig(trader_id=TraderId("QUANT-AUDIT-001"))
    engine = BacktestEngine(config=engine_config)

    venue_name = "BINANCE"
    engine.add_venue(
        venue=Venue(venue_name),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=Currency.from_str("USDT"),
        starting_balances=[Money.from_str(f"{initial_capital:.2f} USDT")],
        fee_model=MakerTakerFeeModel(Decimal("0.0003"), Decimal("0.0003")),
    )

    raw_symbol = f"{symbol_str}USDT"
    instrument_id = InstrumentId(Symbol(raw_symbol), Venue(venue_name))
    instrument = CurrencyPair(
        instrument_id=instrument_id,
        raw_symbol=Symbol(raw_symbol),
        base_currency=Currency.from_str(symbol_str if symbol_str != "GOLD" else "GLD"),
        quote_currency=Currency.from_str("USDT"),
        price_precision=2,
        size_precision=4,
        price_increment=Price.from_str("0.01"),
        size_increment=Quantity.from_str("0.0001"),
        lot_size=Quantity.from_str("0.0001"),
        max_quantity=Quantity.from_str("100000"),
        min_quantity=Quantity.from_str("0.0001"),
        max_price=Price.from_str("1000000.0"),
        min_price=Price.from_str("0.01"),
        ts_event=0,
        ts_init=0,
    )
    engine.add_instrument(instrument)

    # 1. Load Data
    t0 = time.time()
    df_1m = load_asset_1m_data(symbol_str)
    # Take latest 1 year for fast Nautilus native event streaming
    df_1m_slice = df_1m.iloc[-200000:].copy()
    df_macro = aggregate_timeframe_bars(df_1m_slice, macro_tf)
    print(f"Loaded {len(df_1m_slice):,} 1m bars and {len(df_macro):,} {macro_tf} macro bars in {time.time()-t0:.2f}s")

    macro_bar_type_str = f"{raw_symbol}.{venue_name}-3-HOUR-LAST-EXTERNAL" if macro_tf == "3h" else f"{raw_symbol}.{venue_name}-15-MINUTE-LAST-EXTERNAL"
    micro_bar_type_str = f"{raw_symbol}.{venue_name}-1-MINUTE-LAST-EXTERNAL"

    macro_bar_type = BarType.from_str(macro_bar_type_str)
    micro_bar_type = BarType.from_str(micro_bar_type_str)

    # Convert to Nautilus Bar objects
    macro_bars = [
        Bar(
            bar_type=macro_bar_type,
            open=Price(float(row['open']), 2),
            high=Price(float(row['high']), 2),
            low=Price(float(row['low']), 2),
            close=Price(float(row['close']), 2),
            volume=Quantity(float(row['volume']), 4),
            ts_event=int(idx.value),
            ts_init=int(idx.value),
        )
        for idx, row in df_macro.iterrows()
    ]

    micro_bars = [
        Bar(
            bar_type=micro_bar_type,
            open=Price(float(row['open']), 2),
            high=Price(float(row['high']), 2),
            low=Price(float(row['low']), 2),
            close=Price(float(row['close']), 2),
            volume=Quantity(float(row['volume']), 4),
            ts_event=int(idx.value),
            ts_init=int(idx.value),
        )
        for idx, row in df_1m_slice.iterrows()
    ]

    print(f"Streaming {len(macro_bars):,} macro bars + {len(micro_bars):,} micro bars into Nautilus engine...")
    engine.add_data(macro_bars)
    engine.add_data(micro_bars)

    # Configure Strategy
    strat_cfg = NautilusIntraBarMatrixConfig(
        instrument_id=instrument_id,
        macro_bar_type=macro_bar_type,
        micro_bar_type=micro_bar_type,
        limit_pullback_pct=0.002,
        atr_sl_mult=1.2,
        atr_tp_mult=2.4,
        risk_per_trade=0.01,
        max_leverage=3.0,
        max_hold_macro_bars=12
    )
    strategy = NautilusIntraBarMatrixStrategy(strat_cfg)
    engine.add_strategy(strategy)

    print("Running Nautilus Trader event-driven simulation...")
    t_run = time.time()
    engine.run()
    print(f"Simulation completed in {time.time()-t_run:.2f}s.")

    trades = strategy.executed_trades
    total_trades = len(trades)
    wins = [t for t in trades if t['pnl'] > 0]
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0.0
    tot_pnl = sum(t['pnl'] for t in trades)
    ret_pct = (tot_pnl / initial_capital) * 100.0

    print("-" * 85)
    print(f" NAUTILUS TRADER RESULTS ({symbol_str} {macro_tf}):")
    print(f" Total Trades : {total_trades}")
    print(f" Win Rate     : {win_rate:.2f}%")
    print(f" Total Net PnL: ${tot_pnl:,.2f} ({ret_pct:.2f}%)")
    print("-" * 85)


if __name__ == "__main__":
    run_nautilus_native_backtest("BTC", "3h")
