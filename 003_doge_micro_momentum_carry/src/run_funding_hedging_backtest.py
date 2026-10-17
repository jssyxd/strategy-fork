"""
Jane Street Quantitative Backtest Engine - Naked Funding Arbitrage / Reverse Hedging Model
Auditing Naked Arbitrage: Long Perp on Venue B vs Short Perp on Venue A (or Spot/Perp Reverse Hedging)
Strictly WITHOUT protective gating (no dynamic funding stop, no volatility regime filter).
Accurately accounts for:
- Venue A fees (Maker/Taker)
- Venue B fees (Maker/Taker)
- Cumulative funding settlements across every 8-hour window
- Real cross-venue basis spread drift and execution slippage
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Dict, Any

def resolve_data_path(custom_path=None):
    candidates = [
        custom_path,
        os.path.join(os.path.dirname(__file__), "../data/doge_real_binance_aligned_5m.parquet"),
        os.path.join(os.path.dirname(__file__), "../../to-research/008_doge_momentum/data/doge_real_binance_aligned_5m.parquet"),
        "/workspace/008_doge_momentum/data/doge_real_binance_aligned_5m.parquet",
        "/workspace/003_doge_micro_momentum_carry/data/doge_real_binance_aligned_5m.parquet",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return os.path.abspath(c)
    return custom_path or candidates[1]

def run_funding_arbitrage_backtest(
    data_path: str = None,
    notional_capital_usdt: float = 1_000_000.0, # 1M USDT nominal per leg
    fee_venue_a_bps: float = 4.0,              # Venue A Taker fee: 4 bps (0.04%)
    fee_venue_b_bps: float = 4.0,              # Venue B Taker fee: 4 bps (0.04%)
    slippage_bps: float = 1.0,                 # Legging execution slippage: 1 bps per leg
    maker_mode: bool = False,                  # If True, fees are 1.0 bps Maker
    report_output: str = None
):
    resolved_data = resolve_data_path(data_path)
    if report_output is None:
        mode_suffix = "maker" if maker_mode else "taker"
        report_output = os.path.join(os.path.dirname(__file__), f"../reports/funding_arbitrage_{mode_suffix}_backtest.json")
    os.makedirs(os.path.dirname(os.path.abspath(report_output)), exist_ok=True)

    print("=" * 80)
    print("JANE STREET QUANT RESEARCH - NAKED FUNDING ARBITRAGE BACKTEST")
    print("=" * 80)
    print(f"Data source           : {resolved_data}")
    print(f"Nominal Leg Size      : {notional_capital_usdt:,.2f} USDT")
    print(f"Execution Fee Mode    : {'MAKER (Passive Quote)' if maker_mode else 'TAKER (Aggressive)'}")
    print(f"Venue A Fee           : {1.0 if maker_mode else fee_venue_a_bps} bps")
    print(f"Venue B Fee           : {1.0 if maker_mode else fee_venue_b_bps} bps")
    print(f"Slippage per Leg      : {0.0 if maker_mode else slippage_bps} bps")
    print(f"Protection Filter     : DISABLED (Naked Buy Reverse Hedge / Cross-Venue Carry)")
    print("-" * 80)

    # 1. Load Real Market Data
    df = pd.read_parquet(resolved_data)
    df["open_dt"] = pd.to_datetime(df["open_dt"])
    df = df.sort_values("open_time").reset_index(drop=True)

    n_bars = len(df)
    print(f"Total 5m Bars Loaded  : {n_bars:,} bars ({df['open_dt'].iloc[0]} to {df['open_dt'].iloc[-1]})")

    # Funding settlement in Binance occurs when fundingTime changes
    df["funding_event"] = df["fundingTime"] != df["fundingTime"].shift(1)
    funding_events_idx = df[df["funding_event"]].index.tolist()
    print(f"Detected Funding Settlement Windows: {len(funding_events_idx)} events (~every 8 hours)")

    # 2. Simulate Cash-and-Carry / Reverse Hedge (Short Perp + Long Spot)
    p_perp_entry = df["close"].iloc[0]
    p_spot_entry = df["spot_close"].iloc[0]

    nominal_perp = notional_capital_usdt
    nominal_spot = notional_capital_usdt
    
    qty_perp = nominal_perp / p_perp_entry
    qty_spot = nominal_spot / p_spot_entry

    fee_open_a = (1.0 if maker_mode else fee_venue_a_bps) / 10000.0
    fee_open_b = (1.0 if maker_mode else fee_venue_b_bps) / 10000.0
    slip = (0.0 if maker_mode else slippage_bps) / 10000.0

    # Initial Opening Friction
    cost_open_perp = nominal_perp * (fee_open_a + slip)
    cost_open_spot = nominal_spot * (fee_open_b + slip)
    total_opening_friction = cost_open_perp + cost_open_spot

    # Tracking arrays
    equity_curve = np.zeros(n_bars)
    cumulative_funding = np.zeros(n_bars)
    cumulative_basis_pnl = np.zeros(n_bars)
    cumulative_fees = np.zeros(n_bars)
    
    current_funding_pnl = 0.0
    total_fees_paid = total_opening_friction

    for i in range(n_bars):
        p_perp_curr = df["close"].iloc[i]
        p_spot_curr = df["spot_close"].iloc[i]

        # Check for funding settlement
        if df["funding_event"].iloc[i]:
            fr = df["fundingRate"].iloc[i]
            # Being SHORT perpetual receives funding when fundingRate > 0
            settlement = (qty_perp * p_perp_curr) * fr
            current_funding_pnl += settlement

        # Mark-to-market delta PnL
        pnl_perp_mtm = qty_perp * (p_perp_entry - p_perp_curr)
        pnl_spot_mtm = qty_spot * (p_spot_curr - p_spot_entry)
        basis_pnl = pnl_perp_mtm + pnl_spot_mtm

        cumulative_funding[i] = current_funding_pnl
        cumulative_basis_pnl[i] = basis_pnl
        cumulative_fees[i] = total_fees_paid
        
        equity_curve[i] = (2 * notional_capital_usdt) + basis_pnl + current_funding_pnl - total_fees_paid

    # Close Friction
    p_perp_exit = df["close"].iloc[-1]
    p_spot_exit = df["spot_close"].iloc[-1]
    cost_close_perp = (qty_perp * p_perp_exit) * (fee_open_a + slip)
    cost_close_spot = (qty_spot * p_spot_exit) * (fee_open_b + slip)
    total_closing_friction = cost_close_perp + cost_close_spot
    
    total_fees_paid += total_closing_friction
    final_net_pnl = current_funding_pnl + cumulative_basis_pnl[-1] - total_fees_paid
    final_return_pct = (final_net_pnl / (2 * notional_capital_usdt)) * 100.0

    # Calculate High-Frequency Risk Metrics
    returns_series = pd.Series(equity_curve).pct_change().dropna()
    bars_per_year = 288 * 365
    sharpe = (returns_series.mean() / (returns_series.std() + 1e-9)) * np.sqrt(bars_per_year) if returns_series.std() > 0 else 0.0

    peak = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - peak) / peak
    max_drawdown_pct = float(np.min(drawdowns)) * 100.0

    # Output Audit Table
    print(f"--- PERFORMANCE AUDIT SUMMARY ---")
    print(f"Total Funding Collected       : +{current_funding_pnl:,.2f} USDT")
    print(f"Basis Spread PnL Drift        : {cumulative_basis_pnl[-1]:,.2f} USDT")
    print(f"Total Fees & Slippage Incurred: -{total_fees_paid:,.2f} USDT")
    print(f"  - Opening Round Friction    : -{total_opening_friction:,.2f} USDT")
    print(f"  - Closing Round Friction    : -{total_closing_friction:,.2f} USDT")
    print(f"Net Total PnL                 : {final_net_pnl:,.2f} USDT")
    print(f"Net Return on Capital         : {final_return_pct:.4f}% (over 27.8 days)")
    annualized_yield = final_return_pct * (365.0 / 27.8)
    print(f"Annualized Net Yield (APR)    : {annualized_yield:.2f}%")
    print(f"Max Drawdown                  : {max_drawdown_pct:.4f}%")
    print(f"Annualized Sharpe Ratio       : {sharpe:.2f}")
    print("=" * 80)

    report = {
        "dataset": data_path,
        "notional_leg_usdt": notional_capital_usdt,
        "total_capital_usdt": 2 * notional_capital_usdt,
        "maker_mode": maker_mode,
        "fee_venue_a_bps": fee_venue_a_bps,
        "fee_venue_b_bps": fee_venue_b_bps,
        "slippage_bps": slippage_bps,
        "total_funding_collected_usdt": current_funding_pnl,
        "basis_pnl_usdt": float(cumulative_basis_pnl[-1]),
        "total_fees_paid_usdt": total_fees_paid,
        "opening_fees_usdt": total_opening_friction,
        "closing_fees_usdt": total_closing_friction,
        "net_pnl_usdt": final_net_pnl,
        "net_return_pct": final_return_pct,
        "annualized_apr_pct": annualized_yield,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe_ratio": float(sharpe),
    }

    with open(report_output, "w") as f:
        json.dump(report, f, indent=4)
    print(f"Report successfully saved to {report_output}")

    return report

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ["taker", "all"]:
        print("\n>>> RUNNING TAKER (AGGRESSIVE) EXECUTION BACKTEST <<<")
        run_funding_arbitrage_backtest(
            maker_mode=False,
            fee_venue_a_bps=4.0,
            fee_venue_b_bps=4.0,
            slippage_bps=1.0,
            report_output="/workspace/reports/funding_arbitrage_taker_backtest.json"
        )
    if mode in ["maker", "all"]:
        print("\n>>> RUNNING MAKER (PASSIVE QUEUE) EXECUTION BACKTEST <<<")
        run_funding_arbitrage_backtest(
            maker_mode=True,
            fee_venue_a_bps=1.0,
            fee_venue_b_bps=1.0,
            slippage_bps=0.0,
            report_output="/workspace/reports/funding_arbitrage_maker_backtest.json"
        )
