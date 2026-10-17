"""
Jane Street Quantitative Backtest Runner & Evaluation Engine.
Integrates Nautilus Trader Engine, Data Adapters, and Comprehensive Statistical Reports.
"""

import sys
import os
import json
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

from data_adapter import load_doge_databank_5m, load_doge_real_binance_5m
from nautilus_doge_strategy import NautilusDogeMomentumStrategy, DogeMomentumConfig


def run_doge_nautilus_backtest(
    data_source="databank", # "databank" or "binance_real"
    initial_capital_usdt=2083333.33, # ~15,000,000 CNY / 7.20
    trade_size_doge=2000000.0,
    maker_fee=0.0002, # 2 bps
    taker_fee=0.0005, # 5 bps
):
    print("=" * 80)
    print("JANE STREET QUANT RESEARCH - NAUTILUS TRADER PRODUCTION BACKTEST")
    print("=" * 80)
    print(f"Dataset Mode: {data_source}")
    print(f"Initial Capital: {initial_capital_usdt:,.2f} USDT (~{initial_capital_usdt * 7.20:,.2f} CNY)")
    print(f"Trade Order Size: {trade_size_doge:,.0f} DOGE")
    print(f"Fee Model: Maker {maker_fee*10000:.1f} bps, Taker {taker_fee*10000:.1f} bps")
    print("-" * 80)

    # 1. Setup Engine & Venue
    engine_config = BacktestEngineConfig(trader_id=TraderId("JANE-STREET-QUANT-001"))
    engine = BacktestEngine(config=engine_config)

    venue_name = "BINANCE"
    engine.add_venue(
        venue=Venue(venue_name),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        base_currency=Currency.from_str("USDT"),
        starting_balances=[Money.from_str(f"{initial_capital_usdt:.2f} USDT")],
        fee_model=MakerTakerFeeModel(Decimal(str(maker_fee)), Decimal(str(taker_fee))),
    )

    # 2. Add Instrument
    raw_symbol = "DOGEUSDT"
    instrument_id = InstrumentId(Symbol(raw_symbol), Venue(venue_name))
    instrument = CurrencyPair(
        instrument_id=instrument_id,
        raw_symbol=Symbol(raw_symbol),
        base_currency=Currency.from_str("DOGE"),
        quote_currency=Currency.from_str("USDT"),
        price_precision=5,
        size_precision=1,
        price_increment=Price.from_str("0.00001"),
        size_increment=Quantity.from_str("0.1"),
        lot_size=Quantity.from_str("0.1"),
        max_quantity=Quantity.from_str("100000000"),
        min_quantity=Quantity.from_str("0.1"),
        max_price=Price.from_str("1000.0"),
        min_price=Price.from_str("0.00001"),
        ts_event=0,
        ts_init=0,
    )
    engine.add_instrument(instrument)

    # 3. Load Data from W:\database
    bar_type_str = f"{raw_symbol}.{venue_name}-5-MINUTE-LAST-EXTERNAL"
    bar_type = BarType.from_str(bar_type_str)

    t0 = time.time()
    if data_source == "databank":
        candidates_db = [
            "/database/03_governed_lake/nautilus_databank/catalog/data/bar/DOGEUSD.CRYPTO-1-MINUTE-LAST-EXTERNAL",
            "/mnt/w/database/03_governed_lake/nautilus_databank/catalog/data/bar/DOGEUSD.CRYPTO-1-MINUTE-LAST-EXTERNAL",
            "W:/database/03_governed_lake/nautilus_databank/catalog/data/bar/DOGEUSD.CRYPTO-1-MINUTE-LAST-EXTERNAL",
        ]
        db_dir = next((c for c in candidates_db if os.path.exists(c)), candidates_db[0])
        bars, raw_df = load_doge_databank_5m(
            databank_dir=db_dir,
            years=["2023", "2024", "2025"],
            bar_type_str=bar_type_str
        )
    else:
        bars, raw_df = load_doge_real_binance_5m(
            bar_type_str=bar_type_str
        )
    print(f"Data ingestion completed in {time.time() - t0:.2f}s. Adding {len(bars):,} bars to Nautilus engine...")

    t0_data = time.time()
    engine.add_data(bars)
    print(f"Data added in {time.time() - t0_data:.2f}s.")

    # 4. Instantiate & Register Strategy
    strat_config = DogeMomentumConfig(
        instrument_id=instrument_id,
        bar_type=bar_type,
        fast_ema_period=12,
        slow_ema_period=48,
        cvd_window=36,
        vol_surge_window=24,
        leverage=2.0,
        stop_loss_pct=0.020,
        trailing_tp_pct=0.035,
        min_tp_activation_pct=0.015,
        trade_size_doge=trade_size_doge,
    )
    strategy = NautilusDogeMomentumStrategy(config=strat_config)
    engine.add_strategy(strategy)

    # 5. Run Engine Simulation
    print("Executing Nautilus Trader event-driven simulation...")
    t_run = time.time()
    engine.run()
    elapsed = time.time() - t_run
    print(f"Simulation completed in {elapsed:.2f}s. Extracting Nautilus BacktestResult...")

    # 6. Extract Statistics from Engine & BacktestResult
    result = engine.get_result()
    account = engine.portfolio.account(Venue(venue_name))
    balances = account.balances()
    usdt_curr = Currency.from_str("USDT")
    final_balance_usdt = float(balances[usdt_curr].total)
    
    total_net_pnl_usdt = final_balance_usdt - initial_capital_usdt
    total_net_pnl_cny = total_net_pnl_usdt * 7.20
    final_equity_cny = final_balance_usdt * 7.20
    
    orders = engine.cache.orders()
    positions = engine.cache.positions()
    
    # Calculate Days
    if hasattr(raw_df.index, 'min') and isinstance(raw_df.index, pd.DatetimeIndex):
        dt_start = str(raw_df.index.min())
        dt_end = str(raw_df.index.max())
        days = max(1.0, (raw_df.index.max() - raw_df.index.min()).total_seconds() / 86400.0)
    else:
        days = len(bars) * 5.0 / 1440.0
        dt_start = str(result.backtest_start)
        dt_end = str(result.backtest_end)

    tot_ret = total_net_pnl_usdt / initial_capital_usdt
    cagr = ((1.0 + max(-0.99, tot_ret)) ** (365.0 / days) - 1.0) * 100.0 if days > 0 else 0.0

    pnl_stats = result.stats_pnls.get("USDT", {})
    ret_stats = result.stats_returns

    sharpe = ret_stats.get("Sharpe Ratio (252 days)", np.nan)
    sortino = ret_stats.get("Sortino Ratio (252 days)", np.nan)
    profit_factor = ret_stats.get("Profit Factor", np.nan)
    win_rate = pnl_stats.get("Win Rate", np.nan)
    if win_rate is not None and not np.isnan(win_rate):
        win_rate *= 100.0

    summary_metrics = {
        "dataset": data_source,
        "time_range": f"{dt_start} to {dt_end} ({days:.1f} days)",
        "total_bars_processed": len(bars),
        "initial_capital_usdt": initial_capital_usdt,
        "initial_capital_cny": initial_capital_usdt * 7.20,
        "final_equity_usdt": final_balance_usdt,
        "final_equity_cny": final_equity_cny,
        "total_net_pnl_usdt": total_net_pnl_usdt,
        "total_net_pnl_cny": total_net_pnl_cny,
        "total_return_pct": tot_ret * 100.0,
        "cagr_pct": cagr,
        "sharpe_ratio_annualized": sharpe,
        "sortino_ratio_annualized": sortino,
        "profit_factor": profit_factor,
        "win_rate_pct": win_rate,
        "total_orders": len(orders),
        "total_positions": len(positions),
        "avg_winner_usdt": pnl_stats.get("Avg Winner", np.nan),
        "avg_loser_usdt": pnl_stats.get("Avg Loser", np.nan),
        "max_winner_usdt": pnl_stats.get("Max Winner", np.nan),
        "max_loser_usdt": pnl_stats.get("Max Loser", np.nan),
        "execution_speed_bars_per_sec": len(bars) / max(0.001, elapsed),
    }

    # Print Executive Summary
    print("=" * 80)
    print("JANE STREET QUANT RESEARCH - STRATEGY PERFORMANCE AUDIT")
    print("=" * 80)
    for k, v in summary_metrics.items():
        if isinstance(v, float):
            print(f"{k:<35}: {v:,.4f}")
        else:
            print(f"{k:<35}: {v}")
    print("=" * 80)

    # Write JSON report
    report_candidates = [
        os.path.join(os.path.dirname(__file__), f"../reports/nautilus_backtest_{data_source}.json"),
        f"/workspace/reports/nautilus_backtest_{data_source}.json",
    ]
    report_path = report_candidates[0]
    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary_metrics, f, indent=4, default=str)
    print(f"Detailed quantitative report saved to: {report_path}")

    return summary_metrics

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "databank"
    run_doge_nautilus_backtest(data_source=mode)
