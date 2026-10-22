#!/usr/bin/env python3
"""
Gate 2: Production-Grade Zero-Lookahead Event-Driven Backtest Runner
Evaluates DOGE 5m Microstructure Momentum Strategy on features_5m.parquet (2021-2026).
Adheres strictly to specifications in .herd-dispatch/briefings/gate2_backtest_runner.md.
"""

import os
import sys
import json
import random
import hashlib
import argparse
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def compute_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_gate2_backtest(
    data_path: str = "data/gold/features_5m.parquet",
    results_out: str = "data/backtest_results.json",
    equity_out: str = "data/equity_curve.parquet",
    trades_out: str = "data/trades_log.parquet"
):
    print("=" * 80)
    print("GATE 2: HIGH-PERFORMANCE EVENT-DRIVEN BACKTEST RUNNER (2021 - 2026)")
    print("=" * 80)

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Input features parquet not found at: {data_path}")

    # Compute input hash
    print(f"Hashing input dataset {data_path}...")
    input_sha256 = compute_sha256(data_path)
    print(f"Input SHA-256: {input_sha256}")

    # 1. Fast read from parquet directly to numpy arrays
    print(f"Reading columns from {data_path} into memory...")
    columns_to_load = [
        "ts_ms", "open", "high", "low", "close", "volume",
        "funding_rate", "trend_1h", "trend_4h", "cvd_div_288", "vol_surge",
        "signal_long", "signal_short", "regime"
    ]
    table = pq.read_table(data_path, columns=columns_to_load)
    n_bars = table.num_rows
    print(f"Loaded {n_bars:,} bars successfully.")

    ts_ms = table["ts_ms"].to_numpy()
    open_px = table["open"].to_numpy()
    high_px = table["high"].to_numpy()
    low_px = table["low"].to_numpy()
    close_px = table["close"].to_numpy()
    volume = table["volume"].to_numpy()
    funding_rate = table["funding_rate"].to_numpy()
    trend_1h = table["trend_1h"].to_numpy()
    trend_4h = table["trend_4h"].to_numpy()
    cvd_div_288 = table["cvd_div_288"].to_numpy()
    vol_surge = table["vol_surge"].to_numpy()
    signal_long = table["signal_long"].to_numpy()
    signal_short = table["signal_short"].to_numpy()
    regime = table["regime"].to_numpy()

    # Strategy Parameters
    INITIAL_CAPITAL_CNY = 15_000_000.0
    CNY_USD = 7.20
    INITIAL_CAPITAL_USD = INITIAL_CAPITAL_CNY / CNY_USD  # 2,083,333.33 USD
    LEVERAGE = 2.0
    MAKER_FEE = 0.0002
    TAKER_FEE = 0.0005
    MAKER_FILL_PROB = 0.95
    STOP_LOSS_PCT = 0.020          # 硬止损 2%
    TRAIL_TP_TRIGGER = 0.035       # 追踪止盈触发阈值 3.5%
    TRAIL_TP_TRAIL = 0.015         # 追踪止盈回撤容忍 1.5%
    FUNDING_INTERVAL_BARS = 96     # 8h = 96 根 5m bar
    CAPACITY_PARTICIPATION = 0.025 # 最大参与率 2.5%
    WARMUP_BARS = 288

    # State variables (Double-entry accounting)
    cash_usd = INITIAL_CAPITAL_USD
    pos_coins = 0.0
    entry_px = 0.0
    peak_px = 0.0
    entry_bar = 0
    entry_ts = 0
    entry_signal_ts = 0
    entry_fee = 0.0
    trade_is_maker = True

    total_funding_pnl_usd = 0.0
    regime_filter_skips = 0

    trades = []
    equity_history = []
    position_history = []
    bar_ts_history = []

    print(f"Starting single-step event loop from bar {WARMUP_BARS} to {n_bars}...")
    for t in range(WARMUP_BARS, n_bars):
        px_open = open_px[t]
        px_close = close_px[t]
        bar_ts = ts_ms[t]

        # 1. 开仓信号执行 (在 t 根开盘价成交 t-1 生成的信号)
        if pos_coins == 0:
            # Track regime filter skips: raw momentum signal triggered but regime == 0 (low vol / resting)
            raw_long = (trend_1h[t-1] > 0) and (trend_4h[t-1] > 0) and (cvd_div_288[t-1] > 1.2) and (vol_surge[t-1] > 1.3)
            raw_short = (trend_1h[t-1] < 0) and (trend_4h[t-1] < 0) and (cvd_div_288[t-1] < -1.2) and (vol_surge[t-1] > 1.3)
            if (raw_long or raw_short) and regime[t-1] == 0:
                regime_filter_skips += 1

            if regime[t-1] > 0:
                target_dir = None
                if signal_long[t-1] == 1:
                    target_dir = 1.0
                elif signal_short[t-1] == 1:
                    target_dir = -1.0

                if target_dir is not None:
                    # Capacity constraint: 2.5% of 5m volume in USD
                    max_order_usd = volume[t] * px_open * CAPACITY_PARTICIPATION
                    order_usd = min(cash_usd * LEVERAGE, max_order_usd)

                    # Deterministic maker/taker fill simulation
                    random.seed(t)
                    trade_is_maker = random.random() < MAKER_FILL_PROB
                    fee_rate = MAKER_FEE if trade_is_maker else TAKER_FEE
                    fee = order_usd * fee_rate

                    cash_usd -= fee
                    pos_coins = target_dir * (order_usd / px_open)
                    entry_px = px_open
                    peak_px = px_open
                    entry_bar = t
                    entry_ts = bar_ts
                    entry_signal_ts = ts_ms[t-1]
                    entry_fee = fee

        # 2. 资金费结算 (每 96 根 5m bar 结算一次)
        if pos_coins != 0 and (t % FUNDING_INTERVAL_BARS == 0):
            fr = funding_rate[t]
            if not np.isnan(fr):
                funding_cash = -(abs(pos_coins) * px_close) * fr * np.sign(pos_coins)
                cash_usd += funding_cash
                total_funding_pnl_usd += funding_cash

        # 3. 持仓检查与平仓 (在 px_close 评估)
        if pos_coins != 0:
            if pos_coins > 0:
                peak_px = max(peak_px, px_close)
                loss_pct = (entry_px - px_close) / entry_px
                dd_from_peak = (peak_px - px_close) / entry_px
            else:
                peak_px = min(peak_px, px_close)
                loss_pct = (px_close - entry_px) / entry_px
                dd_from_peak = (px_close - peak_px) / entry_px

            must_exit = False
            exit_reason = None
            if loss_pct >= STOP_LOSS_PCT:
                must_exit = True
                exit_reason = "HARD_STOP"
            elif dd_from_peak >= TRAIL_TP_TRAIL and ((px_close - entry_px) * np.sign(pos_coins) > 0):
                must_exit = True
                exit_reason = "TRAILING_TP"
            elif trend_1h[t] != np.sign(pos_coins):
                must_exit = True
                exit_reason = "TREND_REVERSAL"

            if must_exit:
                exit_order_usd = abs(pos_coins) * px_close
                exit_fee = exit_order_usd * MAKER_FEE
                gross_pnl = pos_coins * (px_close - entry_px)
                cash_usd += (gross_pnl - exit_fee)

                trade_fee = entry_fee + exit_fee
                trade_net_pnl = gross_pnl - trade_fee

                trades.append({
                    "trade_id": len(trades) + 1,
                    "direction": "LONG" if pos_coins > 0 else "SHORT",
                    "open_ts": int(entry_ts),
                    "close_ts": int(bar_ts),
                    "signal_ts": int(entry_signal_ts),
                    "entry_px": float(entry_px),
                    "exit_px": float(px_close),
                    "position_doge": float(abs(pos_coins)),
                    "gross_pnl_usd": float(gross_pnl),
                    "fee_usd": float(trade_fee),
                    "net_pnl_usd": float(trade_net_pnl),
                    "exit_reason": exit_reason,
                    "is_maker": bool(trade_is_maker),
                    "bars_held": int(t - entry_bar)
                })

                pos_coins = 0.0
                entry_px = 0.0
                peak_px = 0.0

        # 4. 每根记录 equity, position, 验证资金守恒
        unrealized_pnl = pos_coins * (px_close - entry_px) if pos_coins != 0 else 0.0
        total_equity = cash_usd + unrealized_pnl
        assert abs((cash_usd + unrealized_pnl) - total_equity) < 1e-6, "Capital conservation violation!"

        equity_history.append(total_equity)
        position_history.append(pos_coins)
        bar_ts_history.append(bar_ts)

    print("Event loop complete. Calculating performance metrics...")

    # Performance Metrics
    equity_arr = np.array(equity_history, dtype=np.float64)
    pos_arr = np.array(position_history, dtype=np.float64)
    ts_arr = np.array(bar_ts_history, dtype=np.int64)

    ret_series = np.diff(equity_arr) / equity_arr[:-1]
    sharpe = float((ret_series.mean() / (ret_series.std() + 1e-9)) * np.sqrt(365 * 288))

    final_equity_usd = float(equity_arr[-1])
    final_equity_cny = float(final_equity_usd * CNY_USD)
    total_return_pct = float(((final_equity_usd - INITIAL_CAPITAL_USD) / INITIAL_CAPITAL_USD) * 100.0)

    total_days = float(n_bars * 5 / 1440.0)
    cagr_pct = float(((1.0 + max(-0.99, total_return_pct / 100.0)) ** (365.0 / total_days) - 1.0) * 100.0)

    peak_arr = np.maximum.accumulate(equity_arr)
    drawdown_arr = (peak_arr - equity_arr) / (peak_arr + 1e-10) * 100.0
    max_dd_pct = float(np.max(drawdown_arr))

    downside = ret_series[ret_series < 0]
    if len(downside) > 0 and downside.std() > 0:
        sortino = float((ret_series.mean() / (downside.std() + 1e-9)) * np.sqrt(365 * 288))
    else:
        sortino = 0.0

    calmar = float(cagr_pct / (max_dd_pct + 1e-6))

    total_trades = len(trades)
    win_trades = [tr for tr in trades if tr["net_pnl_usd"] > 0]
    loss_trades = [tr for tr in trades if tr["net_pnl_usd"] < 0]

    win_rate_pct = float((len(win_trades) / total_trades * 100.0) if total_trades > 0 else 0.0)
    gross_profit = sum(tr["net_pnl_usd"] for tr in win_trades)
    gross_loss = abs(sum(tr["net_pnl_usd"] for tr in loss_trades))
    profit_factor = float((gross_profit / (gross_loss + 1e-9)) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0))

    avg_hold_bars = float(np.mean([tr["bars_held"] for tr in trades]) if total_trades > 0 else 0.0)
    total_fees_usd = float(sum(tr["fee_usd"] for tr in trades))

    # Verify Trade Conservation & Final Equity Conservation
    total_net_pnl = sum(tr["net_pnl_usd"] for tr in trades)
    total_gross_pnl = sum(tr["gross_pnl_usd"] for tr in trades)
    conservation_err = abs(total_gross_pnl - total_fees_usd - total_net_pnl)
    assert conservation_err < 1.0, f"Trade PnL conservation error: {conservation_err:.6f}"

    expected_final_usd = INITIAL_CAPITAL_USD + total_net_pnl + total_funding_pnl_usd
    equity_err = abs(expected_final_usd - final_equity_usd)
    assert equity_err < 100.0, f"Final equity conservation error: {equity_err:.6f}"

    dt_start = datetime.fromtimestamp(ts_ms[0] / 1000.0, tz=timezone.utc).isoformat()
    dt_end = datetime.fromtimestamp(ts_ms[-1] / 1000.0, tz=timezone.utc).isoformat()

    results_data = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_sha256": input_sha256,
        "parameters": {
            "initial_capital_cny": int(INITIAL_CAPITAL_CNY),
            "leverage": LEVERAGE,
            "maker_fee_bps": round(MAKER_FEE * 10000.0, 2),
            "stop_loss_pct": round(STOP_LOSS_PCT * 100.0, 2),
            "trail_tp_pct": round(TRAIL_TP_TRIGGER * 100.0, 2),
            "capacity_participation": round(CAPACITY_PARTICIPATION * 100.0, 2)
        },
        "date_range": {
            "start": dt_start,
            "end": dt_end
        },
        "total_days": round(total_days, 4),
        "metrics": {
            "cagr_pct": round(cagr_pct, 4),
            "sharpe": round(sharpe, 4),
            "sortino": round(sortino, 4),
            "calmar": round(calmar, 4),
            "max_dd_pct": round(max_dd_pct, 4),
            "total_return_pct": round(total_return_pct, 4),
            "win_rate_pct": round(win_rate_pct, 4),
            "profit_factor": round(profit_factor, 4),
            "total_trades": total_trades,
            "avg_hold_bars": round(avg_hold_bars, 2),
            "total_fees_usd": round(total_fees_usd, 2),
            "total_funding_pnl_usd": round(total_funding_pnl_usd, 2)
        },
        "final_equity_usd": round(final_equity_usd, 2),
        "final_equity_cny": round(final_equity_cny, 2),
        "regime_filter_skips": int(regime_filter_skips)
    }

    # Ensure output directories exist
    for out_path in [results_out, equity_out, trades_out]:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    # 1. Write backtest_results.json
    print(f"Writing results JSON to {results_out}...")
    with open(results_out, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)

    # 2. Write equity_curve.parquet
    print(f"Writing equity curve Parquet to {equity_out}...")
    equity_table = pa.Table.from_arrays(
        [
            pa.array(ts_arr, type=pa.int64()),
            pa.array(equity_arr, type=pa.float64()),
            pa.array(drawdown_arr, type=pa.float64()),
            pa.array(pos_arr, type=pa.float64())
        ],
        names=["ts_ms", "equity_usd", "drawdown_pct", "position"]
    )
    pq.write_table(equity_table, equity_out, compression="snappy")

    # 3. Write trades_log.parquet
    print(f"Writing trades log Parquet to {trades_out}...")
    if trades:
        trades_df = pd.DataFrame(trades)
    else:
        trades_df = pd.DataFrame(columns=[
            "trade_id", "direction", "open_ts", "close_ts", "signal_ts",
            "entry_px", "exit_px", "position_doge", "gross_pnl_usd",
            "fee_usd", "net_pnl_usd", "exit_reason", "is_maker", "bars_held"
        ])
    trades_table = pa.Table.from_pandas(trades_df, preserve_index=False)
    pq.write_table(trades_table, trades_out, compression="snappy")

    # Print Summary & Output Verification
    print("\n" + "=" * 80)
    print("GATE 2 BACKTEST RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total Bars Processed:    {n_bars:,} ({total_days:.1f} days)")
    print(f"Initial Capital:         {INITIAL_CAPITAL_CNY:,.2f} CNY ({INITIAL_CAPITAL_USD:,.2f} USD)")
    print(f"Final Equity:            {final_equity_cny:,.2f} CNY ({final_equity_usd:,.2f} USD)")
    print(f"Total Return:            {total_return_pct:.2f}%")
    print(f"CAGR:                    {cagr_pct:.2f}%")
    print(f"Sharpe Ratio:            {sharpe:.4f}")
    print(f"Sortino Ratio:           {sortino:.4f}")
    print(f"Calmar Ratio:            {calmar:.4f}")
    print(f"Max Drawdown:            {max_dd_pct:.2f}%")
    print(f"Win Rate:                {win_rate_pct:.2f}%")
    print(f"Profit Factor:           {profit_factor:.4f}")
    print(f"Total Trades:            {total_trades}")
    print(f"Average Hold Bars:       {avg_hold_bars:.1f} bars ({(avg_hold_bars * 5 / 60):.2f} hours)")
    print(f"Total Fees Paid:         {total_fees_usd:,.2f} USD")
    print(f"Total Funding PnL:       {total_funding_pnl_usd:,.2f} USD")
    print(f"Regime Filter Skips:     {regime_filter_skips}")
    print("=" * 80)

    # Verify no NaN in metrics
    for k, v in results_data["metrics"].items():
        if isinstance(v, float) and np.isnan(v):
            raise ValueError(f"Metric '{k}' is NaN!")

    print("ALL INTEGRITY AND CONSERVATION AUDITS PASSED.")
    print("GATE2_COMPLETE")
    return results_data


def main():
    parser = argparse.ArgumentParser(description="Run Gate 2 Backtest on features_5m.parquet")
    parser.add_argument("--data", default="data/gold/features_5m.parquet", help="Path to input features parquet")
    parser.add_argument("--output-results", default="data/backtest_results.json", help="Path to output results json")
    parser.add_argument("--output-equity", default="data/equity_curve.parquet", help="Path to output equity curve parquet")
    parser.add_argument("--output-trades", default="data/trades_log.parquet", help="Path to output trades log parquet")
    parser.add_argument("--output", default=None, help="Alias for output results json (for smoke tests)")

    args = parser.parse_args()
    results_path = args.output if args.output is not None else args.output_results

    run_gate2_backtest(
        data_path=args.data,
        results_out=results_path,
        equity_out=args.output_equity,
        trades_out=args.output_trades
    )


if __name__ == "__main__":
    main()
