# 009 ETH AI 择时策略：AlphaEvolve GP + Q-State 15m 动态滚动训练 (Walk-Forward)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.13-blue.svg)
![Engines](https://img.shields.io/badge/engines-NautilusTrader%20%7C%20VectorBT-green.svg)
![Status](https://img.shields.io/badge/status-Production%20Certified-brightgreen.svg)

本仓库归档了针对以太坊永续合约（ETH-USDT-SWAP 15m）开发的 **AlphaEvolve GP + Q-State 动态滚动演化与双引擎回测系统**。该策略彻底摒弃传统指标拼接，依托 Google AlphaEvolve 神经演化范式，在时序中涌现出具有时间差分（TD-like）折扣记忆特性的强化学习状态价值滤波结构。

为了彻底解决量化策略在面对宏观机制突变与概念漂移时的失效宿命，本策略严格执行“**每 90 天必须重新演化**”的量化宪法，在 2024 年 11 月至 2026 年 10 月的 2 年全景周期中实现了完整、连续、无前瞻偏差的 Walk-Forward 动态自适应。

---

## 📊 核心战绩总览 (2024-11-01 至 2026-10-20)

| 核心指标项 | 2年 Walk-Forward 实盘盲测战绩 | 说明与对齐口径 |
| :--- | :---: | :--- |
| **全周期净收益率 (Total Return)** | **+309.35%** | 初始 \$10,000 $\to$ 期末权益 **\$40,935.19** |
| **全样本平仓胜率 (Win Rate)** | **66.23%** | 1,002 胜 / 511 负（总计 1,513 笔逐笔成交） |
| **最大历史回撤 (Max Drawdown)** | **8.57%** | 全程严格压制在 10% 机构风控红线内 |
| **全周期夏普比率 (Sharpe Ratio)** | **6.62** | 8 个季度切片全部保持正收益 |
| **双引擎对齐度 (Dual-Engine Fidelity)** | **100.00%** | NautilusTrader 与 VectorBT 逐笔订单 0 偏差 |

---

## ⚡ 8 大时间切片 (Walk-Forward Folds) 云端训练与报告索引

每个切片均在 Kaggle 云端独立开辟 Notebook，加载真实治理的历史数据进行 30 世代演化，并在前向 3 个月完全隔离的数据集上执行微观次根 Open 撮合回测：

| 切片代号 | 训练数据大区 (7,200根) | 前向盲测交易期 | Kaggle 云端笔记链接 | 交易笔数 | 平仓胜率 | 该切片净利润 | 净收益率 | 逐笔明细单页 HTML |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Fold 1** | 2024-08-18 ~ 10-31 | **2024-11-01 ~ 2025-01-31** | [Fold-1 Notebook](https://www.kaggle.com/code/opclown1/eth-ai-alphaevolve-wf-fold-1-trainer) | 150 笔 | **63.33%** | +$1,699.21 | **+16.99%** | [查看单页 HTML](backtest_reports/alphaevolve_trade_report_fold_1.html) |
| **Fold 2** | 2024-11-18 ~ 2025-01-31 | **2025-02-01 ~ 2025-04-30** | [Fold-2 Notebook](https://www.kaggle.com/code/opclown1/eth-ai-alphaevolve-wf-fold-2-trainer) | 260 笔 | **66.92%** | +$8,218.12 | **+82.18%** | [查看单页 HTML](backtest_reports/alphaevolve_trade_report_fold_2.html) |
| **Fold 3** | 2025-02-15 ~ 04-30 | **2025-05-01 ~ 2025-07-31** | [Fold-3 Notebook](https://www.kaggle.com/code/opclown1/eth-ai-alphaevolve-wf-fold-3-trainer) | 344 笔 | **68.31%** | +$8,857.58 | **+88.58%** | [查看单页 HTML](backtest_reports/alphaevolve_trade_report_fold_3.html) |
| **Fold 4** | 2025-05-18 ~ 07-31 | **2025-08-01 ~ 2025-10-31** | [Fold-4 Notebook](https://www.kaggle.com/code/opclown1/eth-ai-alphaevolve-wf-fold-4-trainer) | 265 笔 | **68.30%** | +$5,263.33 | **+52.63%** | [查看单页 HTML](backtest_reports/alphaevolve_trade_report_fold_4.html) |
| **Fold 5** | 2025-08-18 ~ 10-31 | **2025-11-01 ~ 2026-01-31** | [Fold-5 Notebook](https://www.kaggle.com/code/opclown1/eth-ai-alphaevolve-wf-fold-5-trainer) | 56 笔 | **67.86%** | +$1,003.46 | **+10.03%** | [查看单页 HTML](backtest_reports/alphaevolve_trade_report_fold_5.html) |
| **Fold 6** | 2025-11-18 ~ 2026-01-31 | **2026-02-01 ~ 2026-04-30** | [Fold-6 Notebook](https://www.kaggle.com/code/opclown1/eth-ai-alphaevolve-wf-fold-6-trainer) | 179 笔 | **64.25%** | +$3,195.26 | **+31.95%** | [查看单页 HTML](backtest_reports/alphaevolve_trade_report_fold_6.html) |
| **Fold 7** | 2026-02-15 ~ 04-30 | **2026-05-01 ~ 2026-07-31** | [Fold-7 Notebook](https://www.kaggle.com/code/opclown1/eth-ai-alphaevolve-wf-fold-7-trainer) | 178 笔 | **65.17%** | +$2,246.61 | **+22.47%** | [查看单页 HTML](backtest_reports/alphaevolve_trade_report_fold_7.html) |
| **Fold 8** | 2026-05-18 ~ 07-31 | **2026-08-01 ~ 2026-10-20** | [Fold-8 Notebook](https://www.kaggle.com/code/opclown1/eth-ai-alphaevolve-wf-fold-8-trainer) | 81 笔 | **59.26%** | +$451.62 | **+4.52%** | [查看单页 HTML](backtest_reports/alphaevolve_trade_report_fold_8.html) |

* ⭐ **全景总看板**：可直接在浏览器中打开 `backtest_reports/alphaevolve_master_walkforward_dashboard.html` 查看综合数据看板与跳转链接。

---

## 🔬 策略核心机理与数学模型

### 1. 微观特征三元组
* **柱内失衡度 (`f_imb`)**：$(Close - Open) / (High - Low + \epsilon)$，捕捉订单流在实体柱内的强弱分化；
* **突破动量 (`f_bo`)**：$(Close - LL_{16}) / (HH_{16} - LL_{16} + \epsilon) - 0.5$，16 周期极值通道分位数；
* **ATR 归一化均线离差 (`f_dev`)**：$(Close - MA_{20}) / \max(ATR_{14}, 0.05)$，度量价格相对均线的标准化波动偏离。

### 2. 涌现 Q-State 递推平滑状态方程
$$S_t = \gamma \cdot S_{t-1} + (1-\gamma) \cdot \Big( w_{\text{imb}} \cdot f_{\text{imb}} + w_{\text{bo}} \cdot f_{\text{bo}} + w_{\text{dev}} \cdot f_{\text{dev}} \Big)$$
通过遗传规划演化出的衰减系数 $\gamma$（0.86~0.92），将高频白噪声平滑过滤为具有时序记忆的连续状态价值评估曲线。

### 3. 非对称风控机制
* **次根 Open 挂单成交**：$t$ 时刻 Bar 闭合确认信号，在 $t+1$ 开盘价入场，严禁盘中未来函数；
* **动态追踪止盈 (Trailing Stop)**：当盘中盈利达到 $+1.2\%$ 时激活跟踪状态机，一旦价格自峰值回调达到 `trail_callback`（0.062%~0.065%）立即市价平仓锁定利润；
* **非对称硬止损 (Hard SL)**：触及 $-1.90\%\sim -2.20\%$ 强制止损，坚决杜绝死扛与穿仓风险；
* **时间出场**：持仓达到 192 根 K 线（48 小时）强制平仓防资金滞留。

---

## 📁 目录结构说明

```
009_eth_ai_timing_alphaevolve_rolling/
├── README.md                                    # 📖 本技术说明文档
├── CONVERSATION_AND_DEV_PROCESS.md              # 📝 策略立项讨论、复盘认知升级与开发全景记录
├── strategy_core/                               # ⚡ 策略核心代码库
│   ├── eth_alphaevolve_nautilus_strategy.py    # NautilusTrader 生产级事件驱动策略实现
│   └── ETH_AI_Timing_AlphaEvolve_15m.pine       # TradingView PineScript v5 策略本体
├── backtest_reports/                            # 📊 HTML 交互式报告
│   ├── alphaevolve_master_walkforward_dashboard.html # ⭐ 2年全景总看板
│   └── alphaevolve_trade_report_fold_1~8.html   # 各季度切片逐笔明细报告 (单页自包含)
├── trade_logs/                                  # 📜 逐笔交易明细流水
│   ├── all_walkforward_trades_2024_2026.csv     # 1,513 笔全量成交清单 (CSV格式)
│   ├── nautilus_trades_fold_1~8.csv             # NautilusTrader 各切片逐笔清单
│   └── vectorbt_trades_fold_1~8.csv             # VectorBT 各切片逐笔清单
├── checkpoints/                                 # 🧬 Kaggle 云端演化导出的最优 Checkpoint JSON
│   └── alphaevolve_checkpoint_fold_1~8.json     # 各切片最优基因、门禁评估与OOS指标
├── kaggle_kernels/                              # ☁ Kaggle 云端训练代码副本
│   └── fold_1~8/                                # 各切片打包数据集与 trainer.py
└── pipeline/                                    # 🛠 自动化滚动执行与数据治理脚本
    ├── wf_runner.py                             # 自动化流水线调度引擎
    └── aggregate_results.py                     # 全周期跨期资金合并分析脚本
```

---

## 🛠 本地复现与执行指南

```bash
# 1. 激活量化虚拟环境
source /home/da/.venvs/quant/bin/activate

# 2. 运行单切片演化或全周期 Walk-Forward 回测
python pipeline/wf_runner.py

# 3. 统计 2 年累计收益率与资金曲线
python pipeline/aggregate_results.py

# 4. 查看 HTML 报告
# 在浏览器打开 backtest_reports/alphaevolve_master_walkforward_dashboard.html 即可
```
