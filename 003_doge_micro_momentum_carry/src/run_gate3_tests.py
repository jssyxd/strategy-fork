#!/usr/bin/env python3
"""
Gate 3: Production-Grade Multi-Tier Test Suite and E2E Browser-Use Auditor.
Executes:
1. Tier 1: Unit Tests (5 Invariants + Zero Look-Ahead + Deterministic Signal + Capital Conservation)
2. Tier 2: Smoke Tests (Cold Start + Extreme Crash + Data Gap Tolerance + Single Large Trade Capacity)
3. Tier 3: HTML Dashboard Generation & Playwright Headless Chromium E2E Browser-Use Verification

Outputs:
- reports/backtest_dashboard.html
- reports/dashboard_screenshot.png
- data/test_report.json
"""

import os
import sys
import json
import tempfile
import traceback
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)
SILVER_PATH = os.path.join(WORKSPACE_DIR, "data/silver/doge_aligned_5m.parquet")
GOLD_PATH = os.path.join(WORKSPACE_DIR, "data/gold/features_5m.parquet")
RESULTS_PATH = os.path.join(WORKSPACE_DIR, "data/backtest_results.json")
EQUITY_PATH = os.path.join(WORKSPACE_DIR, "data/equity_curve.parquet")
TRADES_PATH = os.path.join(WORKSPACE_DIR, "data/trades_log.parquet")
REPORTS_DIR = os.path.join(WORKSPACE_DIR, "reports")
DASHBOARD_HTML_PATH = os.path.join(REPORTS_DIR, "backtest_dashboard.html")
SCREENSHOT_PATH = os.path.join(REPORTS_DIR, "dashboard_screenshot.png")
TEST_REPORT_PATH = os.path.join(WORKSPACE_DIR, "data/test_report.json")


# ==============================================================================
# HTML Dashboard Generator
# ==============================================================================
def generate_dashboard_html(res: dict, trades: pd.DataFrame, equity: pd.DataFrame) -> str:
    """Generates standalone self-contained HTML interactive report with SVG equity curve."""
    metrics = res['metrics']
    eq_vals = equity['equity_usd'].tolist()
    max_eq = max(eq_vals) if eq_vals else 1
    min_eq = min(eq_vals) if eq_vals else 0
    svg_width, svg_height = 800, 200

    def to_svg_x(i):
        return int(i / max(1, len(eq_vals) - 1) * svg_width)

    def to_svg_y(v):
        return int(svg_height - (v - min_eq) / (max_eq - min_eq + 1e-10) * svg_height)

    # Sample points to keep SVG responsive and clean
    step = max(1, len(eq_vals) // 800)
    sample_indices = list(range(0, len(eq_vals), step))
    if sample_indices[-1] != len(eq_vals) - 1:
        sample_indices.append(len(eq_vals) - 1)

    path_points = [f"{'M' if idx == 0 else 'L'}{to_svg_x(i)},{to_svg_y(eq_vals[i])}" for idx, i in enumerate(sample_indices)]
    path_d = " ".join(path_points)

    trades_rows = []
    for _, row in trades.iterrows():
        pnl = row['net_pnl_usd']
        pnl_color = "#00d4aa" if pnl >= 0 else "#ff4d4d"
        trades_rows.append(f"""<tr>
            <td>{row['trade_id']}</td>
            <td>{row['direction']}</td>
            <td>{row['entry_px']:.6f}</td>
            <td>{row['exit_px']:.6f}</td>
            <td style="color:{pnl_color}">{pnl:.2f}</td>
            <td>{row['exit_reason']}</td>
        </tr>""")

    trades_tbody = "\n".join(trades_rows)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DOGE 动量策略回测报告</title>
<style>
body {{
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    background: #0f0f14;
    color: #e0e0e0;
}}
h1 {{
    color: #ffffff;
    font-size: 1.8em;
    margin-bottom: 8px;
}}
.subtitle {{
    color: #888888;
    font-size: 0.95em;
    margin-bottom: 24px;
}}
.metrics-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin: 24px 0;
}}
.metric-card {{
    background: #1a1a2e;
    border: 1px solid #2a2a44;
    border-radius: 8px;
    padding: 18px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}}
.metric-val {{
    font-size: 2.1em;
    font-weight: 700;
    color: #00d4aa;
    margin-bottom: 6px;
}}
.metric-label {{
    font-size: 0.85em;
    color: #9999aa;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.section-title {{
    font-size: 1.3em;
    margin-top: 32px;
    margin-bottom: 12px;
    color: #ffffff;
}}
.chart-container {{
    background: #151522;
    border: 1px solid #2a2a44;
    border-radius: 8px;
    padding: 16px;
}}
svg {{
    width: 100%;
    height: 220px;
    background: #11111a;
    border-radius: 6px;
}}
.table-container {{
    max-height: 480px;
    overflow-y: auto;
    background: #151522;
    border: 1px solid #2a2a44;
    border-radius: 8px;
    margin-top: 16px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85em;
}}
th, td {{
    border: 1px solid #252538;
    padding: 10px 14px;
    text-align: right;
}}
th {{
    background: #1e1e34;
    color: #aaaaee;
    font-weight: 600;
    position: sticky;
    top: 0;
    text-align: center;
}}
td:nth-child(1), td:nth-child(2), td:nth-child(6) {{
    text-align: center;
}}
footer {{
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #252538;
    color: #666677;
    font-size: 0.8em;
    text-align: center;
}}
</style>
</head>
<body>
<h1>🐕 DOGE 非线性动量策略 · 多年回测报告</h1>
<div class="subtitle">回测区间: {res['date_range']['start']} → {res['date_range']['end']}（{res['total_days']:.1f} 天）| 初始资金: {res['parameters']['initial_capital_cny']:,} CNY ({res['parameters']['initial_capital_cny']/7.20:,.2f} USD)</div>

<div class="metrics-grid">
  <div class="metric-card">
    <div id="metric-cagr" class="metric-val">{metrics['cagr_pct']:.2f}%</div>
    <div class="metric-label">年化收益率 CAGR</div>
  </div>
  <div class="metric-card">
    <div id="metric-sharpe" class="metric-val">{metrics['sharpe']:.2f}</div>
    <div class="metric-label">年化夏普比率 Sharpe</div>
  </div>
  <div class="metric-card">
    <div id="metric-maxdd" class="metric-val">{metrics['max_dd_pct']:.2f}%</div>
    <div class="metric-label">最大历史回撤 MaxDD</div>
  </div>
  <div class="metric-card">
    <div id="metric-trades" class="metric-val">{metrics['total_trades']}</div>
    <div class="metric-label">总交易笔数 Trades</div>
  </div>
</div>

<div class="section-title">📈 策略权益曲线 (USD)</div>
<div class="chart-container">
  <svg id="equity-curve-svg" viewBox="0 0 {svg_width} {svg_height}">
    <path d="{path_d}" fill="none" stroke="#00d4aa" stroke-width="1.8"/>
  </svg>
</div>

<div class="section-title">📋 交易明细记录 (共 {len(trades)} 笔)</div>
<div class="table-container">
  <table id="trades-table">
    <thead>
      <tr>
        <th>#</th>
        <th>方向</th>
        <th>开仓均价 (USD)</th>
        <th>平仓均价 (USD)</th>
        <th>净盈亏 (USD)</th>
        <th>平仓原因</th>
      </tr>
    </thead>
    <tbody>
      {trades_tbody}
    </tbody>
  </table>
</div>

<footer>
生成时间: {res['generated_at_utc']} | 回测引擎: Production v1.0.0 | 状态: Double-Entry Conservation Verified
</footer>
</body>
</html>"""
    return html


# ==============================================================================
# Tier 1: Unit Tests
# ==============================================================================
def test_invariant_monotonic():
    """Unit 1: Verify silver ts_ms is strictly monotonic increasing."""
    df = pq.read_table(SILVER_PATH, columns=['ts_ms']).to_pandas()
    ts = df['ts_ms'].values
    assert (np.diff(ts) > 0).all(), "时间戳非严格单调递增"


def test_invariant_no_duplicate():
    """Unit 2: Verify silver ts_ms has zero duplicates."""
    df = pq.read_table(SILVER_PATH, columns=['ts_ms']).to_pandas()
    assert df['ts_ms'].duplicated().sum() == 0, "存在重复时间戳"


def test_invariant_ohlc_geometry():
    """Unit 3: Verify high >= max(open, close) and low <= min(open, close)."""
    df = pq.read_table(SILVER_PATH, columns=['open', 'high', 'low', 'close']).to_pandas()
    assert (df['high'] >= df[['open', 'close']].max(axis=1)).all(), "high < max(open, close)"
    assert (df['low'] <= df[['open', 'close']].min(axis=1)).all(), "low > min(open, close)"


def test_invariant_positive_prices():
    """Unit 4: Verify open, high, low, close > 0."""
    df = pq.read_table(SILVER_PATH, columns=['open', 'high', 'low', 'close']).to_pandas()
    for col in ['open', 'high', 'low', 'close']:
        assert (df[col] > 0).all(), f"{col} 含非正值"


def test_invariant_non_negative_volume():
    """Unit 5: Verify volume >= 0."""
    df = pq.read_table(SILVER_PATH, columns=['volume']).to_pandas()
    assert (df['volume'] >= 0).all(), "volume 含负值"


def test_cvd_no_lookahead():
    """Unit 6: CVD factor zero look-ahead check on first 1000 bars."""
    df = pq.read_table(GOLD_PATH, columns=['taker_buy_volume', 'volume', 'cvd_z_288']).to_pandas()
    df_trunc = df.iloc[:1000].copy()
    delta = df_trunc['taker_buy_volume'] - (df_trunc['volume'] - df_trunc['taker_buy_volume'])
    cvd = delta.cumsum()
    mu = cvd.rolling(288, min_periods=144).mean()
    sigma = cvd.rolling(288, min_periods=144).std()
    cvd_z_recomputed = (cvd - mu) / (sigma + 1e-10)
    pd.testing.assert_series_equal(
        cvd_z_recomputed.reset_index(drop=True),
        df['cvd_z_288'].iloc[:1000].reset_index(drop=True),
        check_names=False, rtol=1e-5
    )


def test_signal_deterministic():
    """Unit 7: Pure function recreation of signal_long and signal_short."""
    cols = ['trend_1h', 'trend_4h', 'cvd_div_288', 'vol_surge', 'regime', 'signal_long', 'signal_short']
    df = pq.read_table(GOLD_PATH, columns=cols).to_pandas()
    manual_long = (
        (df['trend_1h'] > 0) & (df['trend_4h'] > 0) &
        (df['cvd_div_288'] > 1.2) & (df['vol_surge'] > 1.3) &
        (df['regime'] > 0)
    ).astype(int)
    manual_short = (
        (df['trend_1h'] < 0) & (df['trend_4h'] < 0) &
        (df['cvd_div_288'] < -1.2) & (df['vol_surge'] > 1.3) &
        (df['regime'] > 0)
    ).astype(int)
    pd.testing.assert_series_equal(manual_long.reset_index(drop=True), df['signal_long'].reset_index(drop=True), check_names=False)
    pd.testing.assert_series_equal(manual_short.reset_index(drop=True), df['signal_short'].reset_index(drop=True), check_names=False)


def test_capital_conservation():
    """Unit 8: Verify double-entry capital conservation."""
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        res = json.load(f)
    trades = pq.read_table(TRADES_PATH, columns=['net_pnl_usd']).to_pandas()
    initial_usd = 15_000_000.0 / 7.20
    final_usd = res['final_equity_usd']
    total_net_pnl = trades['net_pnl_usd'].sum()
    total_funding = res['metrics'].get('total_funding_pnl_usd', 0.0)
    expected_final = initial_usd + total_net_pnl + total_funding
    diff = abs(expected_final - final_usd)
    assert diff < 100.0, f"资金守恒误差过大: {diff:.4f} USD"


# ==============================================================================
# Tier 2: Smoke Tests
# ==============================================================================
def test_smoke_cold_start():
    """Smoke 1: Verify backtest_results.json completeness and absence of NaNs."""
    assert os.path.exists(RESULTS_PATH), f"Missing {RESULTS_PATH}"
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        res = json.load(f)
    assert "metrics" in res, "Missing 'metrics' key in backtest_results.json"
    assert "final_equity_usd" in res, "Missing 'final_equity_usd'"
    metrics = res['metrics']
    required_metrics = [
        'cagr_pct', 'sharpe', 'sortino', 'calmar', 'max_dd_pct',
        'total_return_pct', 'win_rate_pct', 'profit_factor', 'total_trades'
    ]
    for m in required_metrics:
        assert m in metrics, f"Missing metric {m}"
        val = metrics[m]
        assert val is not None, f"Metric {m} is None"
        if isinstance(val, (int, float)):
            assert not np.isnan(val), f"Metric {m} is NaN"


def test_smoke_extreme_crash():
    """Smoke 2: Simulate single bar -50% flash crash during active position; engine handles gracefully."""
    from src.run_gate2_backtest import run_gate2_backtest

    # Slice 2,000 bars around trade 3 (trade 3 opens at 223242)
    df = pq.read_table(GOLD_PATH).to_pandas().iloc[222000:224000].copy().reset_index(drop=True)
    crash_idx = 1250  # Bar 1250 is during trade 3
    df.loc[crash_idx, 'close'] = df.loc[crash_idx, 'open'] * 0.5
    df.loc[crash_idx, 'low'] = df.loc[crash_idx, 'close']
    df.loc[crash_idx, 'high'] = max(df.loc[crash_idx, 'open'], df.loc[crash_idx, 'close'])

    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as f:
        tmp_parquet = f.name
        df.to_parquet(tmp_parquet)

    tmp_res = tempfile.mktemp(suffix='.json')
    tmp_eq = tempfile.mktemp(suffix='.parquet')
    tmp_tr = tempfile.mktemp(suffix='.parquet')

    try:
        res = run_gate2_backtest(
            data_path=tmp_parquet,
            results_out=tmp_res,
            equity_out=tmp_eq,
            trades_out=tmp_tr
        )
        assert res['final_equity_usd'] > 0, "Extreme crash caused negative equity!"
    finally:
        for p in [tmp_parquet, tmp_res, tmp_eq, tmp_tr]:
            if os.path.exists(p):
                os.remove(p)


def test_smoke_data_gap_tolerance():
    """Smoke 3: Simulate 100-bar data gap; engine handles gracefully."""
    from src.run_gate2_backtest import run_gate2_backtest

    df = pq.read_table(GOLD_PATH).to_pandas().iloc[:2000].copy()
    # Inject 100-bar gap between 800 and 900
    df_gap = pd.concat([df.iloc[:800], df.iloc[900:]]).reset_index(drop=True)

    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as f:
        tmp_parquet = f.name
        df_gap.to_parquet(tmp_parquet)

    tmp_res = tempfile.mktemp(suffix='.json')
    tmp_eq = tempfile.mktemp(suffix='.parquet')
    tmp_tr = tempfile.mktemp(suffix='.parquet')

    try:
        res = run_gate2_backtest(
            data_path=tmp_parquet,
            results_out=tmp_res,
            equity_out=tmp_eq,
            trades_out=tmp_tr
        )
        assert res['final_equity_usd'] > 0, "Data gap caused backtest failure!"
    finally:
        for p in [tmp_parquet, tmp_res, tmp_eq, tmp_tr]:
            if os.path.exists(p):
                os.remove(p)


def test_smoke_single_large_trade():
    """Smoke 4: Simulate low-volume bar; order size must be bounded by capacity constraint."""
    from src.run_gate2_backtest import run_gate2_backtest

    # Slice 1,000 bars (222500:223500) where bar 742 has entry signal
    df = pq.read_table(GOLD_PATH).to_pandas().iloc[222500:223500].copy().reset_index(drop=True)
    trade_bar = 742
    df.loc[trade_bar, 'volume'] = 1000.0  # severely restricted volume

    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as f:
        tmp_parquet = f.name
        df.to_parquet(tmp_parquet)

    tmp_res = tempfile.mktemp(suffix='.json')
    tmp_eq = tempfile.mktemp(suffix='.parquet')
    tmp_tr = tempfile.mktemp(suffix='.parquet')

    try:
        res = run_gate2_backtest(
            data_path=tmp_parquet,
            results_out=tmp_res,
            equity_out=tmp_eq,
            trades_out=tmp_tr
        )
        trades = pq.read_table(tmp_tr).to_pandas()
        capped_trades = trades[trades['open_ts'] == df.loc[trade_bar, 'ts_ms']]
        assert len(capped_trades) == 1, "Capped trade was not recorded"
        t_row = capped_trades.iloc[0]
        expected_notional = 1000.0 * t_row['entry_px'] * 0.025
        actual_notional = t_row['position_doge'] * t_row['entry_px']
        assert abs(actual_notional - expected_notional) < 1e-4, f"Capacity constraint violated: actual={actual_notional}, expected={expected_notional}"
    finally:
        for p in [tmp_parquet, tmp_res, tmp_eq, tmp_tr]:
            if os.path.exists(p):
                os.remove(p)


# ==============================================================================
# Tier 3: E2E Playwright Browser-Use Tests
# ==============================================================================
def run_e2e_playwright_suite():
    """
    Tier 3: E2E Browser-Use verification.
    Launches headless Chromium, navigates to backtest_dashboard.html,
    and runs 6 DOM assertions + saves screenshot.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # 1. Generate reports/backtest_dashboard.html
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        res = json.load(f)
    trades = pq.read_table(TRADES_PATH).to_pandas()
    equity = pq.read_table(EQUITY_PATH).to_pandas()

    html_content = generate_dashboard_html(res, trades, equity)
    with open(DASHBOARD_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)

    dom_results = {}
    e2e_checks = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        file_url = f"file://{os.path.abspath(DASHBOARD_HTML_PATH)}"
        page.goto(file_url)
        page.wait_for_load_state("networkidle")

        # Assertion 1: CAGR card
        try:
            cagr_elem = page.query_selector("#metric-cagr")
            assert cagr_elem is not None, "#metric-cagr element not found"
            cagr_txt = cagr_elem.inner_text().strip()
            assert any(c.isdigit() for c in cagr_txt), f"CAGR text invalid: {cagr_txt}"
            dom_results["cagr_card_present"] = True
            e2e_checks["test_e2e_metric_cagr"] = True
        except Exception as e:
            dom_results["cagr_card_present"] = False
            e2e_checks["test_e2e_metric_cagr"] = str(e)

        # Assertion 2: Sharpe card
        try:
            sharpe_elem = page.query_selector("#metric-sharpe")
            assert sharpe_elem is not None, "#metric-sharpe element not found"
            sharpe_txt = sharpe_elem.inner_text().strip()
            assert any(c.isdigit() for c in sharpe_txt), f"Sharpe text invalid: {sharpe_txt}"
            dom_results["sharpe_card_present"] = True
            e2e_checks["test_e2e_metric_sharpe"] = True
        except Exception as e:
            dom_results["sharpe_card_present"] = False
            e2e_checks["test_e2e_metric_sharpe"] = str(e)

        # Assertion 3: MaxDD card
        try:
            maxdd_elem = page.query_selector("#metric-maxdd")
            assert maxdd_elem is not None, "#metric-maxdd element not found"
            maxdd_txt = maxdd_elem.inner_text().strip()
            assert any(c.isdigit() for c in maxdd_txt), f"MaxDD text invalid: {maxdd_txt}"
            dom_results["maxdd_card_present"] = True
            e2e_checks["test_e2e_metric_maxdd"] = True
        except Exception as e:
            dom_results["maxdd_card_present"] = False
            e2e_checks["test_e2e_metric_maxdd"] = str(e)

        # Assertion 4: Trades count card
        try:
            trades_elem = page.query_selector("#metric-trades")
            assert trades_elem is not None, "#metric-trades element not found"
            trades_txt = trades_elem.inner_text().strip()
            assert trades_txt.isdigit(), f"Trades text not integer: {trades_txt}"
            assert int(trades_txt) == len(trades), f"Trades count mismatch: {trades_txt} vs {len(trades)}"
            e2e_checks["test_e2e_metric_trades"] = True
        except Exception as e:
            e2e_checks["test_e2e_metric_trades"] = str(e)

        # Assertion 5: Equity Curve SVG & non-empty path
        try:
            svg_elem = page.query_selector("#equity-curve-svg")
            assert svg_elem is not None, "#equity-curve-svg element not found"
            dom_results["equity_svg_present"] = True

            paths = page.query_selector_all("#equity-curve-svg path")
            assert len(paths) > 0, "#equity-curve-svg contains no path element"
            path_d = paths[0].get_attribute("d")
            assert path_d is not None and len(path_d.strip()) > 10, "SVG path 'd' attribute is empty or truncated"
            dom_results["equity_svg_has_path"] = True
            e2e_checks["test_e2e_equity_svg"] = True
        except Exception as e:
            dom_results["equity_svg_present"] = dom_results.get("equity_svg_present", False)
            dom_results["equity_svg_has_path"] = False
            e2e_checks["test_e2e_equity_svg"] = str(e)

        # Assertion 6: Trades Table & tbody rows count
        try:
            table_elem = page.query_selector("#trades-table")
            assert table_elem is not None, "#trades-table element not found"
            dom_results["trades_table_present"] = True

            rows = page.query_selector_all("#trades-table tbody tr")
            row_count = len(rows)
            dom_results["trades_table_row_count"] = row_count
            assert row_count == len(trades), f"Table rows mismatch: {row_count} vs {len(trades)}"
            assert row_count > 0, "Trades table tbody has 0 rows"
            e2e_checks["test_e2e_trades_table"] = True
        except Exception as e:
            dom_results["trades_table_present"] = dom_results.get("trades_table_present", False)
            dom_results["trades_table_row_count"] = len(page.query_selector_all("#trades-table tbody tr"))
            e2e_checks["test_e2e_trades_table"] = str(e)

        # Capture and save high-resolution screenshot
        page.screenshot(path=SCREENSHOT_PATH, full_page=True)
        browser.close()

    return dom_results, e2e_checks


# ==============================================================================
# Main Runner & Report Compiler
# ==============================================================================
def main():
    print("=" * 80)
    print("GATE 3: TEST AUDITOR & E2E VERIFICATION SUITE")
    print("=" * 80)

    critical_failures = []

    # 1. Run Unit Tests (8)
    unit_test_list = [
        ("test_invariant_monotonic", test_invariant_monotonic),
        ("test_invariant_no_duplicate", test_invariant_no_duplicate),
        ("test_invariant_ohlc_geometry", test_invariant_ohlc_geometry),
        ("test_invariant_positive_prices", test_invariant_positive_prices),
        ("test_invariant_non_negative_volume", test_invariant_non_negative_volume),
        ("test_cvd_no_lookahead", test_cvd_no_lookahead),
        ("test_signal_deterministic", test_signal_deterministic),
        ("test_capital_conservation", test_capital_conservation),
    ]

    unit_passed = 0
    print("\n--- Running Tier 1: Unit Tests (8) ---")
    for name, fn in unit_test_list:
        try:
            fn()
            unit_passed += 1
            print(f"  [PASS] {name}")
        except Exception as err:
            print(f"  [FAIL] {name}: {err}")
            critical_failures.append(f"Unit test {name} failed: {err}")

    # 2. Run Smoke Tests (4)
    smoke_test_list = [
        ("test_smoke_cold_start", test_smoke_cold_start),
        ("test_smoke_extreme_crash", test_smoke_extreme_crash),
        ("test_smoke_data_gap_tolerance", test_smoke_data_gap_tolerance),
        ("test_smoke_single_large_trade", test_smoke_single_large_trade),
    ]

    smoke_passed = 0
    print("\n--- Running Tier 2: Smoke Tests (4) ---")
    for name, fn in smoke_test_list:
        try:
            fn()
            smoke_passed += 1
            print(f"  [PASS] {name}")
        except Exception as err:
            print(f"  [FAIL] {name}: {err}")
            critical_failures.append(f"Smoke test {name} failed: {err}")

    # 3. Run E2E Playwright Browser-Use Tests (6)
    print("\n--- Running Tier 3: E2E Playwright Browser-Use Tests (6) ---")
    try:
        dom_assertions, e2e_checks = run_e2e_playwright_suite()
        e2e_passed = 0
        for name, res in e2e_checks.items():
            if res is True:
                e2e_passed += 1
                print(f"  [PASS] {name}")
            else:
                print(f"  [FAIL] {name}: {res}")
                critical_failures.append(f"E2E test {name} failed: {res}")
    except Exception as err:
        dom_assertions = {}
        e2e_checks = {}
        e2e_passed = 0
        print(f"  [FAIL] E2E Suite Execution: {err}")
        traceback.print_exc()
        critical_failures.append(f"E2E Suite execution failed: {err}")

    # 4. Compile and Save Test Report
    overall_status = "PASS" if len(critical_failures) == 0 else "FAIL"

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "test_suite_version": "v1.0.0",
        "unit_tests": {
            "total": len(unit_test_list),
            "passed": unit_passed,
            "failed": len(unit_test_list) - unit_passed
        },
        "smoke_tests": {
            "total": len(smoke_test_list),
            "passed": smoke_passed,
            "failed": len(smoke_test_list) - smoke_passed
        },
        "e2e_tests": {
            "total": 6,
            "passed": e2e_passed,
            "failed": 6 - e2e_passed
        },
        "dom_assertions": {
            "sharpe_card_present": dom_assertions.get("sharpe_card_present", False),
            "cagr_card_present": dom_assertions.get("cagr_card_present", False),
            "maxdd_card_present": dom_assertions.get("maxdd_card_present", False),
            "equity_svg_present": dom_assertions.get("equity_svg_present", False),
            "equity_svg_has_path": dom_assertions.get("equity_svg_has_path", False),
            "trades_table_present": dom_assertions.get("trades_table_present", False),
            "trades_table_row_count": dom_assertions.get("trades_table_row_count", 0)
        },
        "overall_status": overall_status,
        "critical_failures": critical_failures
    }

    with open(TEST_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print("TEST REPORT SUMMARY")
    print("=" * 80)
    print(f"Report File:      {TEST_REPORT_PATH}")
    print(f"Dashboard HTML:   {DASHBOARD_HTML_PATH}")
    print(f"Screenshot:       {SCREENSHOT_PATH}")
    print(f"Unit Tests:       {unit_passed}/{len(unit_test_list)} passed")
    print(f"Smoke Tests:      {smoke_passed}/{len(smoke_test_list)} passed")
    print(f"E2E Tests:        {e2e_passed}/6 passed")
    print(f"Overall Status:   {overall_status}")
    print("=" * 80)

    if overall_status == "PASS":
        print("GATE3_COMPLETE")
        sys.exit(0)
    else:
        print(f"Gate 3 Failed with {len(critical_failures)} critical failures.")
        sys.exit(1)


if __name__ == "__main__":
    main()
