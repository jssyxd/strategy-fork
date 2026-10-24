# 009 ETH AI 择时策略：AutoML-Zero 寄存器指令集 + DEAP JIT 动态滚动演化

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.13-blue.svg)
![Engines](https://img.shields.io/badge/engines-NautilusTrader%20%7C%20VectorBT-green.svg)
![Architecture](https://img.shields.io/badge/architecture-AutoML--Zero%20%7C%20DEAP%20JIT-brightgreen.svg)

本目录为仓库官方 **009 号策略**。
系统已全面重构为基于 **Google Research AutoML-Zero (arXiv:2003.03384)** 寄存器指令虚拟机与 **DEAP Numba JIT** 极速编译加速引擎。
策略摒弃了死板的预设公式，由算法从零自主组合微观特征寄存器操作码，在 2024 年 11 月至 2026 年 10 月的 2 年连续时序中实现了 8 个季度的 Walk-Forward 动态滚动交易。

---

## ⚡ 核心战绩总览 (2024-11-01 至 2026-10-20)

| 核心指标项 | 2 年 Walk-Forward 实盘盲测数据 | 机制说明 |
| :--- | :---: | :--- |
| **全周期净收益率 (Total Return)** | **+154.59%** | 初始 \$10,000 $\to$ 期末权益 **\$25,458.89** |
| **全样本平仓胜率 (Win Rate)** | **64.06%** | 966 胜 / 542 负 (总计 1,508 笔真实撮合) |
| **全周期最大回撤 (Max Drawdown)** | **15.92%** | 无任何破产或穿仓风险 |
| **全周期夏普比率 (Sharpe Ratio)** | **3.83** | 扣除 0.07% Taker 手续费与滑点 |
| **单切片云端训练速度** | **~24 秒** | Numba `@njit` 带来上百倍加速，单次模拟仅 0.03 微秒 |
| **双引擎对齐度 (Dual-Engine Fidelity)** | **100.00%** | NautilusTrader 与 VectorBT 逐笔订单 0 偏差 |

---

## 🔬 8 大时间切片 (Walk-Forward Folds) 云端训练与报告索引

每个季度切片均在 Kaggle 云端开辟独立 Notebook，基于真实治理的 7,200 根 15m K 线进行演化，并在前向 3 个月完全未见的数据上执行次根 Open 挂单撮合：

| 切片代号 | 训练数据大区 (7,200根) | 前向盲测交易期 | Kaggle 云端笔记链接 | 交易笔数 | 平仓胜率 | 该切片净利润 | 逐笔明细单页 HTML |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Fold 1** | 2024-08-18 ~ 10-31 | **2024-11-01 ~ 2025-01-31** | [Fold-1 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-automlzero-deap-jit-wf-fold-1-trainer) | 166 笔 | **62.05%** | +$1,727.93 | [单页 HTML](backtest_reports/alphaevolve_automlzero_trade_report_fold_1.html) |
| **Fold 2** | 2024-11-18 ~ 2025-01-31 | **2025-02-01 ~ 2025-04-30** | [Fold-2 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-automlzero-deap-jit-wf-fold-2-trainer) | 116 笔 | **58.62%** | +$1,286.78 | [单页 HTML](backtest_reports/alphaevolve_automlzero_trade_report_fold_2.html) |
| **Fold 3** | 2025-02-15 ~ 04-30 | **2025-05-01 ~ 2025-07-31** | [Fold-3 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-automlzero-deap-jit-wf-fold-3-trainer) | 319 笔 | **58.62%** | -$53.73 | [单页 HTML](backtest_reports/alphaevolve_automlzero_trade_report_fold_3.html) |
| **Fold 4** | 2025-05-18 ~ 07-31 | **2025-08-01 ~ 2025-10-31** | [Fold-4 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-automlzero-deap-jit-wf-fold-4-trainer) | 149 笔 | **71.14%** | +$3,731.29 | [单页 HTML](backtest_reports/alphaevolve_automlzero_trade_report_fold_4.html) |
| **Fold 5** | 2025-08-18 ~ 10-31 | **2025-11-01 ~ 2026-01-31** | [Fold-5 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-automlzero-deap-jit-wf-fold-5-trainer) | 174 笔 | **67.82%** | +$303.00 | [单页 HTML](backtest_reports/alphaevolve_automlzero_trade_report_fold_5.html) |
| **Fold 6** | 2025-11-18 ~ 2026-01-31 | **2026-02-01 ~ 2026-04-30** | [Fold-6 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-automlzero-deap-jit-wf-fold-6-trainer) | 329 笔 | **66.26%** | **+$4,444.92** | [单页 HTML](backtest_reports/alphaevolve_automlzero_trade_report_fold_6.html) |
| **Fold 7** | 2026-02-15 ~ 04-30 | **2026-05-01 ~ 2026-07-31** | [Fold-7 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-automlzero-deap-jit-wf-fold-7-trainer) | 128 笔 | **65.62%** | +$2,351.79 | [单页 HTML](backtest_reports/alphaevolve_automlzero_trade_report_fold_7.html) |
| **Fold 8** | 2026-05-18 ~ 07-31 | **2026-08-01 ~ 2026-10-20** | [Fold-8 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-automlzero-deap-jit-wf-fold-8-trainer) | 127 笔 | **64.57%** | +$1,666.91 | [单页 HTML](backtest_reports/alphaevolve_automlzero_trade_report_fold_8.html) |

* ⭐ **全景总看板**：可直接在浏览器打开 `backtest_reports/master_v1_v2_v3_triathlon_dashboard.html` 查看综合对比看板。

---

## 🛠 AutoML-Zero 寄存器指令虚拟机架构

算法核心运行在轻量级寄存器指令机上：
* **寄存器定义**：
  * $r_0$：柱内失衡度 (`f_imb`)
  * $r_1$：突破动量 (`f_bo`)
  * $r_2$：ATR 归一化均线离差 (`f_dev`)
  * $r_3$：二阶交叉项 ($r_0 \cdot |r_1|$)
  * $r_4$：累加目标寄存器 (`signal_acc`)
  * $r_5$：中间临时寄存器 (`temp`)
* **支持的操作码 (Opcodes)**：
  * `OP 0: dest += w * src`
  * `OP 1: dest -= w * src`
  * `OP 2: dest *= (1.0 + w * src)`
  * `OP 3: dest = tanh(dest + w * src)`
* **Q-State 时序滤波更新**：
  $$S_t = \gamma \cdot S_{t-1} + (1-\gamma) \cdot r_4[t]$$

---

## 📁 目录文件清单

```
009_eth_ai_timing_alphaevolve_rolling/
├── README.md                                    # 📖 本技术规格文档
├── CONVERSATION_AND_DEV_PROCESS.md              # 📝 演进研发全景记录
├── strategy_core/                               # ⚡ 生产级策略实现
│   ├── eth_alphaevolve_nautilus_strategy.py    # NautilusTrader 事件驱动策略
│   └── ETH_AI_Timing_AlphaEvolve_15m.pine       # TradingView PineScript v5 策略
├── backtest_reports/                            # 📊 交互式单页 HTML 报告
│   ├── master_v1_v2_v3_triathlon_dashboard.html# ⭐ 三代对决全景看板
│   └── alphaevolve_automlzero_trade_report_fold_1~8.html # 8个切片逐笔明细报告
├── trade_logs/                                  # 📜 逐笔明细数据表
│   ├── all_automlzero_trades_2024_2026.csv      # 1,508 笔全量成交流水清单
│   ├── nautilus_trades_fold_1~8.csv             # NautilusTrader 各切片逐笔表
│   └── vectorbt_trades_fold_1~8.csv             # VectorBT 各切片逐笔表
├── checkpoints/                                 # 🧬 各切片演化 Checkpoint JSON (含字节码)
│   └── alphaevolve_checkpoint_fold_1~8.json
├── kaggle_kernels/                              # ☁ Kaggle 云端训练代码副本
│   └── fold_1~8/ (含 kernel-metadata.json, trainer.py)
└── pipeline/                                    # 🛠 自动化滚动执行脚本
    └── runner_automlzero_v3.py                  # AutoML-Zero JIT 调度引擎
```
