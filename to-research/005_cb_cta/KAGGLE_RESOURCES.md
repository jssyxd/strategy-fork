# Kaggle 关联资源 (Kaggle Resources) — 策略 005 可转债 CTA（低容量高夏普）

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`convertible bond`、`china bond yield`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `davidlee118856/convertible-bond-empirical-study` | Convertible bond empirical study | 279,302 | 27 | 0 | <https://www.kaggle.com/datasets/davidlee118856/convertible-bond-empirical-study> | 可转债实证研究数据，直接对应双低因子与债底估值的实证口径。 |
| `techsalerator/end-of-day-pricing-market-data-china-techsalerator` | End-of-Day Pricing Market Data China Techsalerator | 17,922 | 43 | 0 | <https://www.kaggle.com/datasets/techsalerator/end-of-day-pricing-market-data-china-techsalerator> | 中国债券/权益类日终定价数据，用于转债底仓与纯债价值参考。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、Notebooks (Kernels)

| ref | 标题 | 作者 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `franciscofeng/usage-of-chinese-bond-data` | Usage of Chinese Bond Data | Francisco Feng | 10 | <https://www.kaggle.com/code/franciscofeng/usage-of-chinese-bond-data> | 中国债券数据处理与使用示例，对应可转债/利率资产的数据管线。 |
| `janskoda/btc-usd-ma-trend-following` | BTC/USD MA trend following | Jan Škoda | 14 | <https://www.kaggle.com/code/janskoda/btc-usd-ma-trend-following> | 均线趋势跟踪实现，可作 CTA 趋势择时层的极简对照实现。 |

拉取：`kaggle kernels pull <ref> -p notebooks/`

---

## 4、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
