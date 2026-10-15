# Kaggle 关联资源 (Kaggle Resources) — 策略 010 BTC 15m 高频波段与资金流追踪

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`bitcoin 15 minute`、`order flow imbalance`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `pranshujayswal/order-flow-imbalance-and-liquidity-stress-btc` | Order Flow Imbalance and Liquidity Stress: BTC | 65,077,671 | 167 | 0 | <https://www.kaggle.com/datasets/pranshujayswal/order-flow-imbalance-and-liquidity-stress-btc> | BTC 订单流不平衡与流动性压力指标，直接对应本策略的资金流突变因子。 |
| `novandraanugrah/bitcoin-historical-datasets-2018-2024` | BITCOIN Historical Datasets 2018-2026 Binance API | 21,060,168 | 28,292 | 198 | <https://www.kaggle.com/datasets/novandraanugrah/bitcoin-historical-datasets-2018-2024> | Binance API 的 BTC 历史数据，用于 15m 波段回测。 |
| `marvingozo/hyperliquid-l1-order-flow-microstructure-10-perps` | Hyperliquid L1 Order Flow Microstructure 10 Perps | 83,036,012,523 | 389 | 0 | <https://www.kaggle.com/datasets/marvingozo/hyperliquid-l1-order-flow-microstructure-10-perps> | 永续合约订单流微观结构，可迁移到 15m 频率的资金流监控。 |
| `waelelghazzawi/multilevel-order-flow-imbalance-panel` | Multilevel Order Flow Imbalance Panel | 1,075,934 | 3 | 0 | <https://www.kaggle.com/datasets/waelelghazzawi/multilevel-order-flow-imbalance-panel> | 多层级订单流不平衡面板，用于构造多档资金流特征。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、Notebooks (Kernels)

| ref | 标题 | 作者 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `sureshmecad/money-flow-index-mfi` | Money Flow Index (MFI) | A SURESH | 18 | <https://www.kaggle.com/code/sureshmecad/money-flow-index-mfi> | 资金流指标 (MFI) 实现，与本策略资金流监控模块同源。 |

拉取：`kaggle kernels pull <ref> -p notebooks/`

---

## 4、竞赛 (Competitions)

| ref | 奖励 | 队伍数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | :--- | :--- |
| `drw-crypto-market-prediction` | ? | ? | <https://www.kaggle.com/competitions/drw-crypto-market-prediction> | 加密市场预测竞赛，可对照高频波段任务的数据与评估。 |

---

## 5、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
