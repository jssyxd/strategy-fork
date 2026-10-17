# 对话关键结论摘要（2026-10-18）

## 数据现状

- **主账户**：2026-10-05 12:43 ~ 10-09 01:52，初始约 219 USDT，风险 5%。策略 PnL +79.3 USDT（自记约 +88.9）。包含完整 decisions_15m.csv、fills、orders、策略版本时间线。
- **Demo 账户**：2026-10-02 ~ 10-15，初始约 95k USDT，风险 1%，杠杆 3x。127 开 / 125 平，总 PnL +11,372 USDT，胜率约 41.6%。CSV 中标的字段为日志 artifact（INFO-SWAP），已通过价格反推 BTC/ETH/SOL/BNB。

两边策略高度同源：Dirichlet 主观逻辑门控（u ≤ 0.35, C < 0.40）、趋势+量能+CLV+波动+回踩评分、组合最多 2 标的、3 连亏熔断。

## 核心问题诊断

10 月 9 日前后发生明显 Regime 切换（清算 cascade，ETH 受损更重），原策略在干净趋势回踩环境表现优异，在后续高噪声环境反复止损。肉眼 K 线变化不大，但微观结构与波动特征已变。

## 方案决策

- **不做**每日连续优化大量浮点参数（过拟合高风险）。
- **做**离散模式分类（TrendFollow / HighSelectivity / Invert / NoTrade）+ LightGBM/XGBoost。
- 严格 Purged Walk-Forward + Embargo，杜绝 lookahead。
- 主账户小资金数据作为最终压力测试集。
- Kaggle 用于重训，本地 cron 负责日常推理与热更新。
- 所有变更必须可审计，与仓库 `anti/` 宪法对齐。

## 推荐实施顺序

1. 清洗统一两边数据，构建特征表 + 标签。
2. 定义离散模式并在历史上评估适用区间。
3. 搭建最小可行 LightGBM + Purged WF 框架。
4. 实现 Data Agent 增量流水线。
5. 接入 Kaggle 与安全闸门 + Nautilus 热更新。

## 关键文件位置（本仓库）

- 方案总览与原则：`docs/01_scheme_overview.md`
- 全模块提示词：`docs/02_modules_and_prompts.md`
- 独立提示词文件：`prompts/`
