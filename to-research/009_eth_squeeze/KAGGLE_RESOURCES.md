# Kaggle 关联资源 (Kaggle Resources) — 策略 009 ETH 波动率挤压 (Vol Squeeze)

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`option implied volatility surface`、`crypto options`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `waelelghazzawi/cboe-sp500-implied-volatility-surface` | CBOE S&P 500 Options Implied Volatility Surface | 2,745,018 | 14 | 0 | <https://www.kaggle.com/datasets/waelelghazzawi/cboe-sp500-implied-volatility-surface> | CBOE 隐含波动率曲面面板，SVI/SSVI 拟合与 IV-RV 偏离研究的直接数据。 |
| `waelelghazzawi/arbitrage-free-ssvi-volatility-surface` | Arbitrage-Free SSVI Volatility Surface Panel | 841,549 | 4 | 0 | <https://www.kaggle.com/datasets/waelelghazzawi/arbitrage-free-ssvi-volatility-surface> | 无套利 SSVI 曲面面板，对应本策略的无套利曲面约束与标定。 |
| `harshitsama/aapl-spy-options-volatility-surface` | AAPL & SPY Options Volatility Surface (2016-2023) | 508,433,702 | 73 | 1 | <https://www.kaggle.com/datasets/harshitsama/aapl-spy-options-volatility-surface> | 个股/ETF 期权波动率曲面，跨标的曲面形态对照。 |
| `bykarantelicom/bykaranteli-crypto-derivatives-data` | ByKaranteli Crypto Derivatives Data (CC0) | 3,753,613 | 5,827 | 1 | <https://www.kaggle.com/datasets/bykarantelicom/bykaranteli-crypto-derivatives-data> | 加密衍生品数据，对应本策略的 ETH 期权/波动率标的。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、Notebooks (Kernels)

| ref | 标题 | 作者 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `oosmansadiq/implied-volatility-surface` | Implied Volatility Surface | Oosman Sadiq | 4 | <https://www.kaggle.com/code/oosmansadiq/implied-volatility-surface> | IV 曲面构建实操，对应本策略曲面拟合层。 |
| `aboobackerpullat/systematic-volatility-engine-multi-strategy` | Systematic Volatility Engine: Multi-Strategy | ABOOBACKER PULLAT | 6 | <https://www.kaggle.com/code/aboobackerpullat/systematic-volatility-engine-multi-strategy> | 系统性波动率多策略引擎，对应本策略按波动率状态切换多腿组合的设计。 |
| `lusfernandotorres/options-trading-long-short-straddle` | Options Trading: Long & Short Straddle 📈 | Luis Torres | 23 | <https://www.kaggle.com/code/lusfernandotorres/options-trading-long-short-straddle> | 跨式/宽跨式期权策略实现，对应本策略 Straddle 腿。 |

拉取：`kaggle kernels pull <ref> -p notebooks/`

---

## 4、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
