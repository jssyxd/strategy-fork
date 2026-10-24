# 012 ETH AI 择时策略：长时序 25,000 根 (260天) 事件驱动动态重训全景实录

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.13-blue.svg)
![Engines](https://img.shields.io/badge/engines-NautilusTrader%20%7C%20VectorBT-green.svg)
![Architecture](https://img.shields.io/badge/architecture-Event--Driven%20%7C%2025k--Bars-brightgreen.svg)

本目录归档了针对以太坊永续合约（ETH-USDT-SWAP 15m）实施的 **长时序 25,000 根 (约 260 天) 事件驱动动态重训实战回放**（2024 年 10 月 1 日 至 2026 年 10 月 20 日全景 71,970 根 K 线）。

系统彻底废弃了固定的机械定周期滚动，改由 **L1~L3 三层 AI 哨兵体系** 依据真实的止损状态、胜率衰减与微观有效性实时监督。一旦触发硬指标（连续 3 笔止损或滚动 20 笔胜率跌破 60%），策略立即强制市价全平并冷冻 48 小时，截取前向 25,000 根跨周期数据在 Kaggle 云端重新演化，通过出厂门禁后无缝上线。

---

## ⚡ 核心实战战绩 (对比固定周期滚动)

| 核心指标项 | 传统固定 90 天切片滚动 (009策略) | **长时序 25,000 根事件驱动重训 (012策略)** | 差异与优化幅度 |
| :--- | :---: | :---: | :---: |
| **全周期交易笔数** | 1,513 笔 | **2,160 笔** | +647 笔 (+42.7%) |
| **全样本平仓胜率** | 66.23% (1,002胜) | **66.53% (1,437胜 / 723负)** | +0.30% (保持高胜率) |
| **2 年全周期净利润** | +$30,935.19 | **+$38,794.51** | **+$7,859.32 (+25.4%)** |
| **全周期总净收益率** | +309.35% | **+387.95%** ($10,000 → $48,794.51) | **+78.60% 爆发提升** |
| **最大历史回撤 (MDD)**| **8.57%** | **9.16%** | +0.59% (严格控制在 10% 以内) |
| **全周期卡玛比率** | 36.09 | **42.37** | **+6.28 跃升** |
| **全周期夏普比率** | 6.62 | **6.21** | 保持高水平 |
| **全周期阶段胜率** | 8/8 全胜 (100%) | **15/15 全胜 (100%)** | 15 个重训阶段无一亏损 |

---

## 🚨 15 大事件驱动重训阶段与下线归因清单

在 2 年连续时序中，系统共捕捉到 14 次真实的哨兵下线事件，并在 Kaggle 云端完成了 15 段 25,000 根跨周期的长时序演化：

| 阶段 | 上线模型代号 | 实战交易区间 | 下线触发规则 (Sentinel Rule) | 下线原因归因 | 交易笔数 | 胜率 | 该段净利润 | Kaggle 云端训练链接 | 逐笔明细单页 |
| :---: | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Seg 1** | AlphaEvolve-Dynamic-Seg1 | 2024-10-01 ~ 11-14 | `TRG-WIN-DECAY` | 滚动 20 笔胜率跌破 60% (实测 50.0%) | 108 笔 | 66.67% | +$1,630.42 | [Seg-1 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-1-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_1.html) |
| **Seg 2** | AlphaEvolve-Dynamic-Seg2 | 2024-11-17 ~ 12-31 | `TRG-WIN-DECAY` | 滚动 20 笔胜率跌破 60% (实测 45.0%) | 123 笔 | 58.54% | +$943.77 | [Seg-2 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-2-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_2.html) |
| **Seg 3** | AlphaEvolve-Dynamic-Seg3 | 2025-01-03 ~ 02-18 | `TRG-WIN-DECAY` | 滚动 20 笔胜率跌破 60% (实测 55.0%) | 147 笔 | 61.90% | +$2,085.21 | [Seg-3 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-3-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_3.html) |
| **Seg 4** | AlphaEvolve-Dynamic-Seg4 | 2025-02-21 ~ 04-07 | `TRG-SL-STREAK` | 连续 3 笔平仓触发硬止损，微观规则失效 | 191 笔 | 74.87% | **+$8,339.95** | [Seg-4 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-4-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_4.html) |
| **Seg 5** | AlphaEvolve-Dynamic-Seg5 | 2025-04-09 ~ 06-13 | `TRG-SL-STREAK` | 连续 3 笔平仓触发硬止损，微观规则失效 | 261 笔 | 72.03% | **+$7,076.50** | [Seg-5 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-5-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_5.html) |
| **Seg 6** | AlphaEvolve-Dynamic-Seg6 | 2025-06-15 ~ 07-31 | `TRG-WIN-DECAY` | 滚动 20 笔胜率跌破 60% (实测 55.0%) | 133 笔 | 71.43% | +$3,104.07 | [Seg-6 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-6-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_6.html) |
| **Seg 7** | AlphaEvolve-Dynamic-Seg7 | 2025-08-03 ~ 09-16 | `TRG-WIN-DECAY` | 滚动 20 笔胜率跌破 60% (实测 50.0%) | 149 笔 | 58.39% | +$232.77 | [Seg-7 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-7-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_7.html) |
| **Seg 8** | AlphaEvolve-Dynamic-Seg8 | 2025-08-04 ~ 09-26 | `TRG-WIN-DECAY` | 滚动 20 笔胜率跌破 60% (实测 55.0%) | 159 笔 | 57.86% | +$74.26 | [Seg-8 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-8-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_8.html) |
| **Seg 9** | AlphaEvolve-Dynamic-Seg9 | 2025-09-30 ~ 11-19 | `TRG-SL-STREAK` | 连续 3 笔平仓触发硬止损，微观规则失效 | 230 笔 | 67.83% | **+$5,368.49** | [Seg-9 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-9-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_9.html) |
| **Seg 10**| AlphaEvolve-Dynamic-Seg10| 2025-11-22 ~ 2026-01-15 | `TRG-WIN-DECAY` | 滚动 20 笔胜率跌破 60% (实测 55.0%) | 111 笔 | 65.77% | +$962.50 | [Seg-10 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-10-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_10.html) |
| **Seg 11**| AlphaEvolve-Dynamic-Seg11| 2026-01-20 ~ 03-09 | `TRG-SL-STREAK` | 连续 3 笔平仓触发硬止损，微观规则失效 | 143 笔 | 69.23% | +$3,569.78 | [Seg-11 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-11-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_11.html) |
| **Seg 12**| AlphaEvolve-Dynamic-Seg12| 2026-03-12 ~ 05-28 | `TRG-WIN-DECAY` | 滚动 20 笔胜率跌破 60% (实测 55.0%) | 112 笔 | 68.75% | +$1,776.94 | [Seg-12 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-12-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_12.html) |
| **Seg 13**| AlphaEvolve-Dynamic-Seg13| 2026-05-31 ~ 07-29 | `TRG-SL-STREAK` | 连续 3 笔平仓触发硬止损，微观规则失效 | 154 笔 | 65.58% | +$1,762.77 | [Seg-13 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-13-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_13.html) |
| **Seg 14**| AlphaEvolve-Dynamic-Seg14| 2026-08-02 ~ 09-29 | `TRG-SL-STREAK` | 连续 3 笔平仓触发硬止损，微观规则失效 | 101 笔 | 64.36% | +$1,016.85 | [Seg-14 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-14-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_14.html) |
| **Seg 15**| AlphaEvolve-Dynamic-Seg15| 2026-10-02 ~ 10-20 | `END_OF_DATA` | 已运行至历史数据集终点 2026-10-20 | 38 笔 | 68.42% | +$850.23 | [Seg-15 Kernel](https://www.kaggle.com/code/opclown1/eth-ai-dynamic-event-seg-15-trainer) | [单页 HTML](reports/alphaevolve_event_trade_report_seg_15.html) |

* ⭐ **全景总看板**：可在浏览器直接打开 [`reports/master_event_driven_dashboard.html`](reports/master_event_driven_dashboard.html) 查看全局资金曲线、回撤分布与分段报告。

---

## 🔬 为什么长时序事件驱动带来 +25.4% 净利润的大幅提升？

1. **摆脱了固定 90 天人为截断的“早熟惩罚”**：
   在行情平稳、当前模型顺风顺水时（例如 Seg 4 和 Seg 5），模型连续运行了近 4 个月，单段分别斩获 **+\$8,339** 与 **+\$7,076** 暴利；传统模式在 90 天硬性换模，导致策略被迫下线，错失了单边行情的主升浪。
2. **25,000 根 (260天) 带来跨周期极强防御力**：
   原本 7,200 根（约 75 天）容易受到局部 2 个月单一极端行情的误导；而 25,000 根强制跨越了至少 1 轮完整牛熊洗盘，演化出的参数面对复杂市场具有天然的“抗震荡免疫力”。
3. **L3 熔断器切除极端尾部风险**：
   一旦市场出现假突破导致连续 3 次触及 2% 止损，系统绝不抱侥幸心理死扛，立即全平并冷冻 48 小时。这一机制精准规避了以太坊多次连续插针的次生灾害。
