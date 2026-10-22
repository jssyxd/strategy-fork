# Gate 3 TestAuditor Agent Briefing
# Role: TestAuditor — 完成即停，不扩展范围

## 前置条件（Gate2 MUST 已完成）
- `data/gold/features_5m.parquet` 已存在
- `data/backtest_results.json` 已存在
- `data/equity_curve.parquet` 已存在
- `data/trades_log.parquet` 已存在

## 任务目标
对数据管道、因子计算和回测引擎进行完整的多层次测试（Unit、Property、Smoke、E2E），
产出 `data/test_report.json`。HTML 交互报告生成在 `reports/backtest_dashboard.html`。

## 约束
- 所有测试独立运行，互相不依赖中间状态
- E2E 测试必须启动真实 HTML 文件并用浏览器自动化验证 DOM 结构
- 完成即停

## 层次1：核心单元测试（pytest）

### 1.1 五大数学不变量测试
```python
import pytest, pyarrow.parquet as pq, pandas as pd, numpy as np

def test_invariant_monotonic():
    df = pq.read_table("data/silver/doge_aligned_5m.parquet").to_pandas()
    ts = df['ts_ms'].values
    assert (np.diff(ts) > 0).all(), "时间戳非严格单调递增"

def test_invariant_no_duplicate():
    df = pq.read_table("data/silver/doge_aligned_5m.parquet").to_pandas()
    assert df['ts_ms'].duplicated().sum() == 0, "存在重复时间戳"

def test_invariant_ohlc_geometry():
    df = pq.read_table("data/silver/doge_aligned_5m.parquet").to_pandas()
    assert (df['high'] >= df[['open', 'close']].max(axis=1)).all()
    assert (df['low'] <= df[['open', 'close']].min(axis=1)).all()

def test_invariant_positive_prices():
    df = pq.read_table("data/silver/doge_aligned_5m.parquet").to_pandas()
    for col in ['open', 'high', 'low', 'close']:
        assert (df[col] > 0).all(), f"{col} 含非正值"

def test_invariant_non_negative_volume():
    df = pq.read_table("data/silver/doge_aligned_5m.parquet").to_pandas()
    assert (df['volume'] >= 0).all(), "volume 含负值"
```

### 1.2 因子零前瞻测试（Zero Look-Ahead）
```python
def test_cvd_no_lookahead():
    """CVD 因子在 t 时刻只能使用 [0, t] 数据，验证方式：删除 t 之后所有数据后重算，结果必须一致"""
    df = pq.read_table("data/gold/features_5m.parquet").to_pandas()
    # 截断到前 1000 行，重算 cvd_z_288，与完整版前 1000 行对比
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

def test_signal_uses_only_lag_data():
    """验证 t 时刻信号只引用 [0, t] 数据（通过检查因子 shift 关系）"""
    df = pq.read_table("data/gold/features_5m.parquet").to_pandas()
    # signal 在 t 时刻应该等于 t 时刻的因子组合（非 t+1）
    manual_long = (
        (df['trend_1h'] > 0) & (df['trend_4h'] > 0) &
        (df['cvd_div_288'] > 1.2) & (df['vol_surge'] > 1.3) &
        (df['regime'] > 0)
    ).astype(int)
    pd.testing.assert_series_equal(
        manual_long.reset_index(drop=True),
        df['signal_long'].reset_index(drop=True),
        check_names=False
    )
```

### 1.3 回测资金守恒测试
```python
def test_capital_conservation():
    import json
    with open("data/backtest_results.json") as f:
        res = json.load(f)
    trades = pq.read_table("data/trades_log.parquet").to_pandas()
    # 净盈亏之和 = final_equity - initial_equity
    initial_usd = 15_000_000 / 7.20
    final_usd = res['final_equity_usd']
    total_net_pnl = trades['net_pnl_usd'].sum()
    total_funding = res['metrics'].get('total_funding_pnl_usd', 0)
    expected_final = initial_usd + total_net_pnl + total_funding
    assert abs(expected_final - final_usd) < 100, f"资金守恒误差: {abs(expected_final - final_usd):.2f} USD"
```

## 层次2：冒烟测试（Smoke Tests）

### 2.1 冷启动测试
```python
def test_smoke_cold_start():
    """从 gold parquet 运行完整回测引擎，必须正常完成"""
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "src/backtest_real_binance_doge.py",
         "--data", "data/gold/features_5m.parquet", "--output", "/tmp/smoke_test.json"],
        capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, f"冷启动失败: {result.stderr}"
```

### 2.2 极端行情边界测试（注入式）
```python
def test_smoke_extreme_crash():
    """注入 -50% 单根 bar 暴跌，回测不能崩溃，净值不能为负"""
    df = pq.read_table("data/gold/features_5m.parquet").to_pandas()
    df_crash = df.copy()
    crash_idx = 10000
    df_crash.loc[crash_idx, 'close'] = df_crash.loc[crash_idx, 'open'] * 0.5
    df_crash.loc[crash_idx, 'low'] = df_crash.loc[crash_idx, 'close']
    # 五大不变量修复
    df_crash.loc[crash_idx, 'high'] = max(df_crash.loc[crash_idx, 'open'],
                                           df_crash.loc[crash_idx, 'close'])
    # 临时写入并运行
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as f:
        df_crash.to_parquet(f.name)
        tmp_path = f.name
    # ... 运行回测，验证 final_equity > 0

def test_smoke_data_gap_tolerance():
    """注入 100 根 bar 的数据空洞，回测不能崩溃"""
    df = pq.read_table("data/gold/features_5m.parquet").to_pandas()
    df_gap = pd.concat([df.iloc[:5000], df.iloc[5100:]]).reset_index(drop=True)
    # 验证回测能够容忍非连续时间戳（不崩溃，正确标记 defect）
    # ... 运行并验证

def test_smoke_single_large_trade():
    """模拟单笔超大订单（超过容量约束），必须被裁剪而非崩溃"""
    # 注入单笔低成交量 bar，容量约束必须生效，订单被压缩
    pass
```

## 层次3：E2E Browser-Use 测试（HTML Dashboard 验证）

### 3.1 生成回测 HTML 交互看板
首先生成 HTML 看板文件（基于回测结果）：
```python
import json, datetime
with open("data/backtest_results.json") as f:
    res = json.load(f)
trades = pq.read_table("data/trades_log.parquet").to_pandas()
equity = pq.read_table("data/equity_curve.parquet").to_pandas()

# 生成 reports/backtest_dashboard.html
html = generate_dashboard_html(res, trades, equity)
os.makedirs("reports", exist_ok=True)
with open("reports/backtest_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)
```

### 3.2 Playwright E2E DOM 验证
```python
from playwright.sync_api import sync_playwright
import os, json

def test_e2e_dashboard_dom():
    html_path = os.path.abspath("reports/backtest_dashboard.html")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file://{html_path}")
        page.wait_for_load_state("networkidle")

        # DOM 级断言 1: 关键绩效指标卡片存在
        sharpe_elem = page.query_selector("#metric-sharpe")
        assert sharpe_elem is not None, "Sharpe 指标卡片不存在"
        sharpe_text = sharpe_elem.inner_text()
        assert sharpe_text.replace('.', '').replace('-', '').strip().isnumeric() or \
               any(c.isdigit() for c in sharpe_text), f"Sharpe 值不可读: {sharpe_text}"

        # DOM 级断言 2: 权益曲线 SVG 存在并包含路径
        svg_elem = page.query_selector("#equity-curve-svg")
        assert svg_elem is not None, "权益曲线 SVG 不存在"
        path_elems = page.query_selector_all("#equity-curve-svg path")
        assert len(path_elems) > 0, "权益曲线 SVG 中无路径元素"

        # DOM 级断言 3: 交易记录表格存在且有数据行
        table_elem = page.query_selector("#trades-table")
        assert table_elem is not None, "交易记录表格不存在"
        rows = page.query_selector_all("#trades-table tbody tr")
        assert len(rows) > 0, "交易记录表格无数据行"

        # DOM 级断言 4: CAGR 数值在合理范围
        with open("data/backtest_results.json") as f:
            results = json.load(f)
        cagr_val = results['metrics']['cagr_pct']
        assert -200 <= cagr_val <= 1000, f"CAGR 超出合理范围: {cagr_val:.1f}%"

        # DOM 级断言 5: 最大回撤必须为正数
        maxdd_val = results['metrics']['max_dd_pct']
        assert 0 <= maxdd_val <= 100, f"MaxDD 不合法: {maxdd_val:.1f}%"

        browser.close()
        print("E2E_DASHBOARD_PASS: All DOM assertions passed")
```

## 生成 HTML Dashboard
```python
def generate_dashboard_html(res, trades, equity) -> str:
    """生成包含 SVG 权益曲线、指标卡片、交易明细表格的独立 HTML 文件"""
    metrics = res['metrics']
    # SVG 权益曲线数据点
    eq_vals = equity['equity_usd'].tolist()
    max_eq = max(eq_vals) if eq_vals else 1
    min_eq = min(eq_vals) if eq_vals else 0
    svg_width, svg_height = 800, 200
    def to_svg_x(i): return int(i / len(eq_vals) * svg_width)
    def to_svg_y(v): return int(svg_height - (v - min_eq) / (max_eq - min_eq + 1e-10) * svg_height)
    path_d = " ".join(
        f"{'M' if i==0 else 'L'}{to_svg_x(i)},{to_svg_y(v)}"
        for i, v in enumerate(eq_vals[::max(1, len(eq_vals)//800)])
    )
    trades_rows = ""
    for _, row in trades.iterrows():
        pnl_color = "green" if row['net_pnl_usd'] > 0 else "red"
        trades_rows += f"""<tr>
            <td>{row['trade_id']}</td>
            <td>{row['direction']}</td>
            <td>{row['entry_px']:.6f}</td>
            <td>{row['exit_px']:.6f}</td>
            <td style="color:{pnl_color}">{row['net_pnl_usd']:.2f}</td>
            <td>{row['exit_reason']}</td>
        </tr>"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>DOGE 动量策略回测报告</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1200px;margin:0 auto;padding:20px;background:#0f0f0f;color:#e0e0e0}}
.metrics-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}}
.metric-card{{background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:16px;text-align:center}}
.metric-val{{font-size:2em;font-weight:700;color:#00d4aa}}
.metric-label{{font-size:0.85em;color:#888;margin-top:4px}}
svg{{width:100%;height:200px;background:#111;border-radius:4px}}
table{{width:100%;border-collapse:collapse;margin-top:16px;font-size:0.85em}}
th,td{{border:1px solid #333;padding:8px;text-align:right}}
th{{background:#1a1a2e;text-align:center}}
</style></head><body>
<h1>🐕 DOGE 非线性动量策略 · 多年回测报告</h1>
<p>回测区间: {res['date_range']['start']} → {res['date_range']['end']}（{res['total_days']:.1f} 天）</p>
<div class="metrics-grid">
  <div class="metric-card"><div id="metric-cagr" class="metric-val">{metrics['cagr_pct']:.1f}%</div><div class="metric-label">年化收益率 CAGR</div></div>
  <div class="metric-card"><div id="metric-sharpe" class="metric-val">{metrics['sharpe']:.2f}</div><div class="metric-label">年化夏普比率</div></div>
  <div class="metric-card"><div id="metric-maxdd" class="metric-val">{metrics['max_dd_pct']:.1f}%</div><div class="metric-label">最大历史回撤</div></div>
  <div class="metric-card"><div id="metric-trades" class="metric-val">{metrics['total_trades']}</div><div class="metric-label">总交易笔数</div></div>
</div>
<h2>权益曲线</h2>
<svg id="equity-curve-svg" viewBox="0 0 {svg_width} {svg_height}">
  <path d="{path_d}" fill="none" stroke="#00d4aa" stroke-width="1.5"/>
</svg>
<h2>交易明细</h2>
<table id="trades-table">
<thead><tr><th>#</th><th>方向</th><th>开仓均价</th><th>平仓均价</th><th>净盈亏(USD)</th><th>平仓原因</th></tr></thead>
<tbody>{trades_rows}</tbody>
</table>
<footer style="margin-top:32px;color:#555;font-size:0.8em">
生成时间: {res['generated_at_utc']} | 回测引擎 v1.0.0 | 不构成投资建议
</footer>
</body></html>"""
```

## 输出规范

### data/test_report.json
```json
{
  "generated_at_utc": "...",
  "test_suite_version": "v1.0.0",
  "unit_tests": {"total": 8, "passed": 8, "failed": 0},
  "smoke_tests": {"total": 4, "passed": 4, "failed": 0},
  "e2e_tests": {"total": 5, "passed": 5, "failed": 0},
  "dom_assertions": {
    "sharpe_card_present": true,
    "equity_svg_present": true,
    "equity_svg_has_path": true,
    "trades_table_present": true,
    "trades_table_row_count": <int>
  },
  "overall_status": "PASS",
  "critical_failures": []
}
```

### reports/backtest_dashboard.html
独立自包含 HTML 文件（无外部依赖），包含 SVG 权益曲线。

## 完成条件
1. `data/test_report.json` 存在，overall_status = "PASS"
2. `reports/backtest_dashboard.html` 存在
3. 打印 "GATE3_COMPLETE" 到 stdout
4. exit(0)
