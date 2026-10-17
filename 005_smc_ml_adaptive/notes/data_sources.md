# 数据源说明

## 主账户导出包

- 文件：`SMC_main_20261005-20261009_export.zip`（对话附件）
- 内容：
  - `README.md`：区间口径、策略版本时间线、规则说明
  - `decisions_15m.csv`：每 15m × 4 币完整决策日志
  - `trades_fills.csv` / `trades_orders.csv`
  - `events_summary.md`
  - `strategies/v3_20261007_1830_rollback3.py`（及其他版本）

## Demo 账户导出包

- 文件：`DEMO_TRADING_AND_STRATEGY_SINCE_20261002_UTC0125.tar.gz`
- 内容：
  - `DEMO_TRADES_AND_15M_DECISIONS_SINCE_20261002.csv`（266 行事件）
  - `DECISION_RULES_EXPLANATION.md`
  - `smc_live_trader_demo_running.py`
  - `smc_health.py`、`docker-compose.yml`

## 使用建议

1. 主账户 decisions_15m.csv 提供最细粒度的特征对齐。
2. Demo 账户提供更长样本与真实盈亏标签。
3. 训练时两者合并，但以时间顺序严格切分，Demo 后期与主账户重叠期可作为交叉验证参考。
4. 原始附件建议另行备份到私有存储或本仓库的 data/ 子目录（注意体积与敏感信息）。
