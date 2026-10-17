# 005 SMC ML Adaptive Regime

**状态**: 研究中 / 自动化流水线设计完成（2026-10-18）

基于主账户（小资金实盘 2026-10-05~10-09）与 Demo 账户（~95k 权益，2026-10-02~10-15，200+ 开平仓）的真实交易日志，构建 **Regime-Aware 离散模式切换 + LightGBM/XGBoost** 的自适应参数系统。

核心目标：在尽量避免过拟合与严格杜绝 lookahead bias 的前提下，根据市场 regime 变化（尤其是 10 月 9 日前后风格切换）动态调整策略行为（包括可能的反指标）。

---

## 核心设计原则（强制）

1. **反 Lookahead Bias**
   - 所有特征只使用当前 bar 及之前信息。
   - 标签的“实现时间”与训练样本之间强制 **Purge + Embargo**。
   - 严格 Walk-Forward / Combinatorial Purged CV，禁止随机 K-Fold 或未来信息泄漏。

2. **反过拟合**
   - 优先 **离散模式分类**（TrendFollow / HighSelectivity / Invert / NoTrade），而非常连续参数每日暴力搜索。
   - 寻找参数“平台”而非尖峰。
   - 主账户小资金真实交易作为高压测试集。
   - 模式切换设置置信度门槛 + 冷却期 + 熔断。

---

## 数据基础

| 账户 | 时间范围 | 规模 | 关键文件来源 |
|------|----------|------|--------------|
| 主账户（小资金） | 2026-10-05 ~ 10-09 | 初始 ~219 U，风险 5% | `SMC_main_20261005-20261009_export.zip` |
| Demo 账户 | 2026-10-02 ~ 10-15 | 初始 ~95k U，风险 1%，杠杆 3x | `DEMO_TRADING_AND_STRATEGY_SINCE_20261002_UTC0125.tar.gz` |

两边策略逻辑高度同源（Dirichlet u/C 门控 + 趋势回踩评分 + 组合最多 2 标的 + 3 连亏熔断）。

---

## 模块架构

```
[每日 Cron / Hermes Agent]
        │
        ▼
┌───────────────────────┐
│ Module 1: Data Agent  │  增量拉取最新 15m K线
└──────────┬────────────┘
           ▼
┌───────────────────────┐
│ Module 2: Feature &   │  特征工程 + 离散模式标签（严格无未来）
│ Label Builder         │
└──────────┬────────────┘
           ▼
┌───────────────────────┐
│ Module 3: Kaggle      │  Purged Walk-Forward + LightGBM/XGBoost
│ Training Agent        │
└──────────┬────────────┘
           ▼
┌───────────────────────┐
│ Module 4: Safety Gate │  置信度 + 熔断 + 审计
└──────────┬────────────┘
           ▼
┌───────────────────────┐
│ Module 5: Nautilus    │  热更新运行参数
│ Hot-Update Agent      │
└───────────────────────┘
```

详细提示词与执行规范见 `docs/` 与 `prompts/`。

---

## 推荐 Kaggle 参考方案

1. **主骨架**：[Purged Time Series CV, XGBoost, Optuna](https://www.kaggle.com/code/marketneutral/purged-time-series-cv-xgboost-optuna)
2. **Regime 补充**：[DRW: XGBoost + LGBM + Regimes](https://www.kaggle.com/code/digantabhattacharya/drw-xgboost-lgbm-regimes-baseline-model)
3. **严格多路径**：[Combinatorial Purged Group K Fold](https://www.kaggle.com/code/gogo827jz/combinatorial-purged-group-k-fold)

---

## 目录结构

```
005_smc_ml_adaptive/
├── README.md                 # 本文件
├── docs/
│   ├── 01_scheme_overview.md
│   ├── 02_modules_and_prompts.md
│   └── 03_conversation_key_points.md
├── prompts/
│   ├── module1_data_agent.md
│   ├── module2_feature_label.md
│   ├── module3_kaggle_train.md
│   ├── module4_safety_gate.md
│   └── module5_nautilus_hotupdate.md
└── notes/
    └── data_sources.md
```

---

## 与仓库宪法的对齐

本方案完全遵循根目录 `anti/` 中的《量化投研反造假与反大模型幻觉审计规范》：
- 强制 Purged + Embargo
- 禁止未来函数
- 真实交易日志优先于回测幻想
- 所有模式切换必须可审计

---

*创建日期: 2026-10-18*
*来源对话: Grok 会话（主账户导出 + Demo 导出 + ML 自适应方案设计）*
