# Kaggle 关联资源 (Kaggle Resources) — 策略 008 DOGE 非线性动量

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`cryptocurrency prices`、`memecoin`、`solana transactions`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `sudalairajkumar/cryptocurrencypricehistory` | Cryptocurrency Historical Prices | 1,782,192 | 114,613 | 1232 | <https://www.kaggle.com/datasets/sudalairajkumar/cryptocurrencypricehistory> | 加密货币历史价格（高下载量），情绪/动量因子的基础面板。 |
| `jessevent/all-crypto-currencies` | Every Cryptocurrency Daily Market Price | 23,593,378 | 22,703 | 549 | <https://www.kaggle.com/datasets/jessevent/all-crypto-currencies> | 全币种日频行情，用于横截面选币与动量排序。 |
| `taniaj/cryptocurrency-market-history-coinmarketcap` | Complete Cryptocurrency Market History | 13,999,088 | 8,385 | 181 | <https://www.kaggle.com/datasets/taniaj/cryptocurrency-market-history-coinmarketcap> | CoinMarketCap 全市场历史，含市值/成交量，用于流动性过滤。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、Notebooks (Kernels)

| ref | 标题 | 作者 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `corneliuskristianto/crypto-technical-indicator-and-ml-prediction` | Crypto Technical Indicator and ML Prediction | Cornelius Kristianto | 123 | <https://www.kaggle.com/code/corneliuskristianto/crypto-technical-indicator-and-ml-prediction> | 加密技术指标 + 机器学习预测，对应本策略微观情绪因子 + 非线性动量建模。 |
| `kadekpadmadarmawan/solana-memecoin-analysis-2026` | Solana Memecoin Analysis 2026 | Kadek Padma Darmawan | 1 | <https://www.kaggle.com/code/kadekpadmadarmawan/solana-memecoin-analysis-2026> | Solana 迷因币分析，直接对应本策略的高弹性代币情绪与脆弱性刻画。 |

拉取：`kaggle kernels pull <ref> -p notebooks/`

---

## 4、竞赛 (Competitions)

| ref | 奖励 | 队伍数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | :--- | :--- |
| `drw-crypto-market-prediction` | ? | ? | <https://www.kaggle.com/competitions/drw-crypto-market-prediction> | 加密市场预测竞赛，对应加密动量的评估与做市/预测任务设定。 |

---

## 5、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
