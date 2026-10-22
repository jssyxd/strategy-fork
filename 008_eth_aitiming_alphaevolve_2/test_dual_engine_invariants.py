#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-End Invariant Test Suite for Dual-Engine Backtest Suite.
Asserts mathematical, causal, and reporting invariants across NautilusTrader & VectorBT.
"""
import json
import math
import os
import sys
from pathlib import Path
import pandas as pd


def test_invariants():
    print("=" * 70)
    print("RUNNING END-TO-END INVARIANT TEST SUITE")
    print("=" * 70)

    # 1. Metric Files Exist
    nt_m_path = Path("reports/nautilus_metrics.json")
    vbt_m_path = Path("reports/vectorbt_metrics.json")
    comp_m_path = Path("reports/dual_engine_comparison.json")
    val_m_path = Path("reports/data_validation_report.json")

    assert nt_m_path.exists(), "Missing nautilus_metrics.json"
    assert vbt_m_path.exists(), "Missing vectorbt_metrics.json"
    assert comp_m_path.exists(), "Missing dual_engine_comparison.json"
    assert val_m_path.exists(), "Missing data_validation_report.json"

    with open(nt_m_path) as f: nt_m = json.load(f)
    with open(vbt_m_path) as f: vbt_m = json.load(f)
    with open(comp_m_path) as f: comp_m = json.load(f)
    with open(val_m_path) as f: val_m = json.load(f)

    # Invariant: Data audit
    assert val_m["audit_passed"] is True, "Data lake audit did not pass"
    assert val_m["target_window"]["actual_bars"] == 1632, "Target window bars != 1632"
    assert val_m["num_gaps_15m"] == 0, "Data lake has gaps"
    assert val_m["duplicate_timestamps"] == 0, "Data lake has duplicate timestamps"
    assert val_m["is_monotonic_increasing"] is True, "Data lake timestamps not strictly monotonic"
    print("[PASS] Invariant 1: Data lake integrity & continuity confirmed.")

    # Invariant: Dual-engine concordance
    assert comp_m["dual_engine_match_rate_pct"] == 100.0, "Match rate != 100.0%"
    assert comp_m["bar_direction_concordance_pct"] == 100.0, "Direction concordance != 100.0%"
    assert comp_m["bar_units_concordance_pct"] == 100.0, "Units concordance != 100.0%"
    assert comp_m["bar_equity_concordance_pct"] == 100.0, "Equity concordance != 100.0%"
    assert len(comp_m["mismatches"]) == 0, f"Mismatches found: {comp_m['mismatches']}"
    print("[PASS] Invariant 2: Dual-engine trade and bar-level concordance confirmed.")

    # Invariant: Portfolio KPIs
    for k in ["total_return_pct", "win_rate_pct", "sharpe_ratio", "sortino_ratio", "calmar_ratio", "max_drawdown_pct", "profit_factor", "total_trades"]:
        val_nt = nt_m[k]
        val_vbt = vbt_m[k]
        assert math.isclose(val_nt, val_vbt, abs_tol=1e-2), f"KPI {k} mismatch: NT={val_nt}, VBT={val_vbt}"
    print("[PASS] Invariant 3: Top-level portfolio KPIs match 100% across engines.")

    # Invariant: Expected target metrics
    assert nt_m["total_trades"] == 38, f"Expected 38 trades, got {nt_m['total_trades']}"
    assert nt_m["winning_trades"] == 31, f"Expected 31 wins, got {nt_m['winning_trades']}"
    assert nt_m["losing_trades"] == 7, f"Expected 7 losses, got {nt_m['losing_trades']}"
    assert nt_m["total_return_pct"] == 4.59, f"Expected +4.59%, got {nt_m['total_return_pct']}%"
    assert nt_m["final_equity"] == 784.45, f"Expected 784.45 USDT, got {nt_m['final_equity']}"
    print("[PASS] Invariant 4: Strategy execution outputs strictly match ground truth targets.")

    # Invariant: End-of-period open position
    nt_open = nt_m.get("open_position_at_end", {})
    vbt_open = vbt_m.get("open_position_at_end", {})
    assert nt_open.get("pos_side") == 1 and vbt_open.get("pos_side") == 1, "Open position not LONG"
    assert math.isclose(nt_open.get("units", 0.0), 0.2803, abs_tol=1e-3), f"Expected 0.2803 units, got {nt_open.get('units')}"
    assert math.isclose(vbt_open.get("units", 0.0), 0.2803, abs_tol=1e-3), f"Expected 0.2803 units, got {vbt_open.get('units')}"
    assert math.isclose(nt_open.get("avg_price", 0.0), 2458.88, abs_tol=1e-2), f"Expected 2458.88 avg px, got {nt_open.get('avg_price')}"
    assert math.isclose(nt_open.get("unrealized_pnl", 0.0), -3.03, abs_tol=1e-2), f"Expected -3.03 unrealized, got {nt_open.get('unrealized_pnl')}"
    print("[PASS] Invariant 5: End-of-period open position strictly verified.")

    # Invariant: Report deliverables existence
    expected_reports = [
        "reports/nautilus_backtest_report.html",
        "reports/nautilus_backtest_report.md",
        "reports/vectorbt_backtest_report.html",
        "reports/vectorbt_backtest_report.md",
        "reports/dual_engine_audit_report.html",
        "reports/dual_engine_audit_report.md",
        "reports/dual_engine_comparison.csv",
        "reports/dual_engine_comparison.md",
        "reports/nautilus_trades.csv",
        "reports/vectorbt_trades.csv",
        "reports/data_validation_report.md",
        "reports/data_validation_report.json",
        "reports/nautilus_trades.json",
        "reports/vectorbt_trades.json",
    ]
    for r in expected_reports:
        p = Path(r)
        assert p.exists() and p.stat().st_size > 0, f"Report {r} missing or empty"

    bom = b"\xef\xbb\xbf"
    for csv_file in ["reports/nautilus_trades.csv", "reports/vectorbt_trades.csv", "reports/dual_engine_comparison.csv"]:
        with open(csv_file, "rb") as fh:
            assert fh.read(3) == bom, f"CSV {csv_file} missing UTF-8 BOM for Excel compatibility"
        df_check = pd.read_csv(csv_file)
        assert len(df_check) == 38, f"CSV {csv_file} expected 38 trade rows, got {len(df_check)}"

    df_nt = pd.read_csv("reports/nautilus_trades.csv")
    df_vbt = pd.read_csv("reports/vectorbt_trades.csv")
    pd.testing.assert_frame_equal(df_nt, df_vbt)

    df_nt_eq = pd.read_csv("reports/nautilus_equity.csv")
    df_vbt_eq = pd.read_csv("reports/vectorbt_equity.csv")
    pd.testing.assert_frame_equal(df_nt_eq, df_vbt_eq)
    print(f"[PASS] Invariant 6: All {len(expected_reports)} deliverable reports & CSVs verified (UTF-8 BOM + exact DataFrame parity).")
    print("ALL INVARIANT TESTS PASSED SUCCESSFULLY (100.0% CONCORDANCE)")
    print("=" * 70)


if __name__ == "__main__":
    test_invariants()
