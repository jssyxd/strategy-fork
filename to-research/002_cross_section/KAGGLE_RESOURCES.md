# Kaggle 关联资源 (Kaggle Resources) — 策略 002 A 股全市场截面选股

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`stock factor alpha`、`china a share stock`、`quantitative factor`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `waelelghazzawi/quantitative-alpha-factor-feature-store-for-ml` | Quantitative Alpha Factor Feature Store for ML | 0 | 1 | 0 | <https://www.kaggle.com/datasets/waelelghazzawi/quantitative-alpha-factor-feature-store-for-ml> | 面向机器学习的量化 Alpha 因子特征库，对应本策略的因子面板与特征工程层。 |
| `stevenchen116/stockchina-minute` | StockChina-minute | 12,090,445,708 | 5,329 | 2 | <https://www.kaggle.com/datasets/stevenchen116/stockchina-minute> | 中国 A 股分钟级行情，是本策略截面选股的本地化数据来源。 |
| `jakewright/9000-tickers-of-stock-market-data-full-history` | 9000+ Tickers of Stock Market Data (Full History) | 1,918,054,636 | 7,557 | 67 | <https://www.kaggle.com/datasets/jakewright/9000-tickers-of-stock-market-data-full-history> | 9000+ 标的全历史行情，用于跨市场截面回测与稳健性检验。 |
| `iamsouravbanerjee/nifty500-stocks-dataset` | Stock Market Dataset (NIFTY-500) | 35,684 | 7,756 | 154 | <https://www.kaggle.com/datasets/iamsouravbanerjee/nifty500-stocks-dataset> | 新兴市场宽基成分股数据，可作 A 股之外的截面泛化对照。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、Notebooks (Kernels)

| ref | 标题 | 作者 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `tomwarrens/temporal-fusion-transformer-in-pytorch` | Temporal Fusion Transformer in PyTorch 🚀🏄‍♂️ | Tommaso Guerrini | 354 | <https://www.kaggle.com/code/tomwarrens/temporal-fusion-transformer-in-pytorch> | Temporal Fusion Transformer 实现，与本策略注意力截面建模的架构层互为参照。 |

拉取：`kaggle kernels pull <ref> -p notebooks/`

---

## 4、竞赛 (Competitions)

| ref | 奖励 | 队伍数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | :--- | :--- |
| `jpx-tokyo-stock-exchange-prediction` | ? | ? | <https://www.kaggle.com/competitions/jpx-tokyo-stock-exchange-prediction> | 大规模股票截面预测竞赛，其评估口径（Rank IC / 收益预测）可直接对照本策略的截面评价体系。 |

---

## 5、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
