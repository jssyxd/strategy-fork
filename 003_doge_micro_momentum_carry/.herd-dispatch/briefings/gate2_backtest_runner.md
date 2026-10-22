# Gate 2 BacktestRunner Agent Briefing
# Role: BacktestRunner — 完成即停，不扩展范围

## 前置条件（Gate1 MUST 已完成）
- `data/gold/features_5m.parquet` 已存在
- `data/factor_report.json` 存在

## 任务目标
在 `data/gold/features_5m.parquet` 上运行无前瞻事件驱动回测引擎，
产出 `data/backtest_results.json` 与 `data/equity_curve.parquet`。

## 约束
- 完全基于已计算的信号列（signal_long, signal_short），不在回测内重算因子
- 信号 t 生成后，最早在 t+1 根 bar 开盘时成交（严禁当根 close 成交）
- Maker Post-Only 挂单：以 t+1 开盘价挂单，挂单成功率模拟 = 95%（5%滑点退化为 taker）
- Maker 手续费 2bps（0.0002），taker 手续费 5bps（0.0005）
- 容量惩罚：单笔订单 USD 名义值不超过 5 分钟窗口成交量×close 的 2.5%
- 完成即停

## 回测引擎规格

### 参数
```python
INITIAL_CAPITAL_CNY = 15_000_000.0
CNY_USD = 7.20
LEVERAGE = 2.0
MAKER_FEE = 0.0002
TAKER_FEE = 0.0005
MAKER_FILL_PROB = 0.95
STOP_LOSS_PCT = 0.020          # 硬止损 2%
TRAIL_TP_TRIGGER = 0.035       # 追踪止盈触发阈值 3.5%
TRAIL_TP_TRAIL = 0.015         # 追踪止盈回撤容忍 1.5%
FUNDING_INTERVAL_BARS = 96     # 8h = 96 根 5m bar
CAPACITY_PARTICIPATION = 0.025 # 最大参与率 2.5%
```

### 双录记账体系
```python
# 仓位状态
pos_coins = 0.0       # 持仓数量（正=多头，负=空头）
entry_px = 0.0        # 开仓均价
peak_px = 0.0         # 追踪止盈峰值价格
cash_usd = initial_capital_usd  # 可用现金（扣手续费后）
unrealized_pnl = 0.0  # 浮动盈亏

# 每根 bar 结束时必须验证
assert abs((cash_usd + unrealized_pnl) - total_equity) < 1e-6
```

### 主循环逻辑（事件驱动，严格单步）
```python
for t in range(WARMUP_BARS, len(df)):
    px_open = df['open'].iloc[t]   # t 根 bar 开盘价 = t-1 信号的成交价格
    px = df['close'].iloc[t]       # t 根 bar 收盘价（用于计算浮盈）

    # 1. 资金费结算（每 96 根）
    if pos_coins != 0 and t % FUNDING_INTERVAL_BARS == 0:
        fr = df['funding_rate'].iloc[t]  # funding_rate 字段（NaN时跳过）
        if pd.notna(fr):
            funding_cash = -(abs(pos_coins) * px) * fr * np.sign(pos_coins)
            cash_usd += funding_cash

    # 2. 容量约束检查
    vol_usd = df['volume'].iloc[t] * px  # 当根 5m 成交量 USD
    max_order_usd = vol_usd * CAPACITY_PARTICIPATION

    # 3. 持仓管理（在 t 根开盘价 = t-1 信号触发的 t 开盘成交）
    # 注意：t-1 信号在 t 开盘执行
    sig_prev = df['signal_long'].iloc[t-1]  # t-1 时刻的信号
    sig_short_prev = df['signal_short'].iloc[t-1]

    # 4. 平仓检查（在 px 即 close 价格评估）
    if pos_coins != 0:
        if pos_coins > 0:
            peak_px = max(peak_px, px)
            loss_pct = (entry_px - px) / entry_px
            dd_from_peak = (peak_px - px) / entry_px
        else:
            peak_px = min(peak_px, px)
            loss_pct = (px - entry_px) / entry_px
            dd_from_peak = (px - peak_px) / entry_px

        must_exit = False
        exit_reason = None
        if loss_pct >= STOP_LOSS_PCT:
            must_exit = True; exit_reason = "HARD_STOP"
        elif dd_from_peak >= TRAIL_TP_TRAIL and (px - entry_px) * np.sign(pos_coins) > 0:
            must_exit = True; exit_reason = "TRAILING_TP"
        elif df['trend_1h'].iloc[t] != np.sign(pos_coins):
            must_exit = True; exit_reason = "TREND_REVERSAL"

        if must_exit:
            # 用 Regime Filter: regime==0 时不开新仓，但平仓正常执行
            order_usd = abs(pos_coins) * px
            fee = order_usd * MAKER_FEE
            pnl = pos_coins * (px - entry_px) - fee
            cash_usd += pnl
            record_trade(...)
            pos_coins = 0.0; entry_px = 0.0; peak_px = 0.0

    # 5. 开仓信号执行（在 t 开盘价，基于 t-1 信号）
    if pos_coins == 0 and df['regime'].iloc[t-1] > 0:  # Regime Filter: 低波动期不开仓
        target_dir = None
        if sig_prev == 1:  target_dir = 1
        elif sig_short_prev == 1: target_dir = -1

        if target_dir is not None:
            order_usd = min(cash_usd * LEVERAGE, max_order_usd)  # 容量约束
            # Maker fill simulation
            import random; random.seed(t)  # 确定性种子
            is_maker = random.random() < MAKER_FILL_PROB
            fee_rate = MAKER_FEE if is_maker else TAKER_FEE
            fee = order_usd * fee_rate
            cash_usd -= fee
            pos_coins = target_dir * (order_usd / px_open)
            entry_px = px_open
            peak_px = px_open

    # 6. 浮盈计算
    unrealized_pnl = pos_coins * (px - entry_px) if pos_coins != 0 else 0.0
    equity_curve.append(cash_usd + unrealized_pnl)
```

## 绩效指标计算
```python
equity_arr = np.array(equity_curve)
ret_series = np.diff(equity_arr) / equity_arr[:-1]
sharpe = (ret_series.mean() / (ret_series.std() + 1e-9)) * np.sqrt(365 * 288)
total_ret = (equity_arr[-1] - initial_usd) / initial_usd
days = len(df) * 5 / 1440.0
cagr = ((1 + max(-0.99, total_ret)) ** (365.0 / days) - 1) * 100
peak = np.maximum.accumulate(equity_arr)
max_dd = np.max((peak - equity_arr) / (peak + 1e-10)) * 100
sortino = (ret_series.mean() / (ret_series[ret_series < 0].std() + 1e-9)) * np.sqrt(365 * 288)
calmar = cagr / (max_dd + 1e-6)
```

## 输出规范

### data/backtest_results.json
```json
{
  "generated_at_utc": "...",
  "input_sha256": "<gold parquet hash>",
  "parameters": {
    "initial_capital_cny": 15000000,
    "leverage": 2.0,
    "maker_fee_bps": 2.0,
    "stop_loss_pct": 2.0,
    "trail_tp_pct": 3.5,
    "capacity_participation": 2.5
  },
  "date_range": {"start": "...", "end": "..."},
  "total_days": <float>,
  "metrics": {
    "cagr_pct": <float>,
    "sharpe": <float>,
    "sortino": <float>,
    "calmar": <float>,
    "max_dd_pct": <float>,
    "total_return_pct": <float>,
    "win_rate_pct": <float>,
    "profit_factor": <float>,
    "total_trades": <int>,
    "avg_hold_bars": <float>,
    "total_fees_usd": <float>,
    "total_funding_pnl_usd": <float>
  },
  "final_equity_usd": <float>,
  "final_equity_cny": <float>,
  "regime_filter_skips": <int>
}
```

### data/equity_curve.parquet
列: ts_ms(int64), equity_usd(float64), drawdown_pct(float64), position(float64)

### data/trades_log.parquet
列: trade_id, direction, open_ts, close_ts, entry_px, exit_px,
    position_doge, gross_pnl_usd, fee_usd, net_pnl_usd, exit_reason, is_maker

## 完成条件
1. `data/backtest_results.json` 存在，所有 metrics 均为非 NaN 浮点数
2. `data/equity_curve.parquet` 与 `data/trades_log.parquet` 存在
3. 打印 "GATE2_COMPLETE" 到 stdout，同时打印核心指标摘要
4. exit(0)
