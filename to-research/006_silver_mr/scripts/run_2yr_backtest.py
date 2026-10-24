#!/usr/bin/env python3
"""
Strategy 06: Silver Mean Reversion (SMR) - 2-Year Event-Driven Backtest Runner
Loads packaged 2-year 15m dataset (2024-10 to 2026-10) and runs full MLOps simulation.
"""

import sys
import os
import json
import time
from pathlib import Path
import pandas as pd
import numpy as np

# Set package root
pkg_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pkg_root))

from engine.dynamic_smr_runner import DynamicSilverSMREngine

def main():
    print("================================================================================")
    print("  STRATEGY 06: SILVER SMR 2-YEAR EVENT-DRIVEN WALK-FORWARD BACKTEST")
    print("================================================================================")
    
    data_file = pkg_root / "data" / "SILVER_AG_2yr_15m.parquet"
    if not data_file.exists():
        print(f"Error: dataset not found at {data_file}")
        sys.exit(1)

    print(f"Loading continuous 2-year dataset from {data_file.name}...")
    t0 = time.time()
    df_ag = pd.read_parquet(data_file)
    t1 = time.time()
    print(f"Loaded {len(df_ag):,} bars in {t1 - t0:.2f}s ({df_ag['datetime'].iloc[0]} to {df_ag['datetime'].iloc[-1]}).")

    engine = DynamicSilverSMREngine(train_window_bars=5760)
    print("Running event-driven simulation with online MLE and creator triggers...")
    res = engine.run_event_driven_backtest(df_ag)
    t2 = time.time()
    print(f"Simulation completed in {t2 - t1:.2f}s.")

    fifo = res["fifo_accounting"]
    print("\n--------------------------------------------------------------------------------")
    print("  EXECUTIVE BACKTEST SUMMARY")
    print("--------------------------------------------------------------------------------")
    print(f"Total Bars Evaluated:           {res['total_bars']:,} bars")
    print(f"Dynamic Retrain Count:          {res['retrain_events_count']} times (~40 days interval)")
    print(f"Toxic Impulse Gate Blocks:      {res['toxic_impulse_blocks']:,} toxic flow spikes blocked")
    print(f"Initial Capital Base:           100,000.00 RMB")
    print(f"Final Total Equity:             {res['total_equity_curve_final']:,.2f} RMB")
    print(f"Total Net Return:               {res['total_return_pct']:+.2f}%")
    print(f"Max Dynamic Drawdown:           {res['max_drawdown_pct']:.2f}%")
    print(f"Sharpe Ratio:                   {res['sharpe_ratio']:.2f}")
    print(f"Calmar Ratio:                   {res['calmar_ratio']:.2f}")
    print("\n[STRICT FIFO ROUND-TRIP INVENTORY MATCHING]")
    print(f"Completed Round-Trips:          {fifo['round_trips_count']:,}")
    print(f"Winning Round-Trips:            {fifo['winning_trades']:,}")
    print(f"Losing Round-Trips:             {fifo['losing_trades']:,} (Adverse Selection)")
    print(f"Realized Win Rate:              {fifo['win_rate_pct']:.2f}%")
    print(f"Profit Factor:                  {fifo['profit_factor']:.2f}")
    print(f"Total Realized Net PnL:         +{fifo['total_net_pnl_rmb']:,.2f} RMB")
    print(f"Average Net PnL / Round-Trip:   +{fifo['avg_pnl_per_trade_rmb']:.2f} RMB/kg")

    reports_dir = pkg_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "SILVER_SMR_2YR_BACKTEST_REPORT.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nDetailed report saved to: {report_path}")

if __name__ == "__main__":
    main()
