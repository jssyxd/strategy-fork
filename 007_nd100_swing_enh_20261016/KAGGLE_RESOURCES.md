# Kaggle 关联资源 (Kaggle Resources) — 策略 004 纳斯达克 100 ETF 增强

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`nasdaq 100 historical`、`option implied volatility`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `novandraanugrah/nasdaq-100-nas100-historical-price-data` | NASDAQ 100 (NAS100) Historical Price Data | 51,370,175 | 11,684 | 116 | <https://www.kaggle.com/datasets/novandraanugrah/nasdaq-100-nas100-historical-price-data> | 纳指 100 历史价格，本策略指数复制端的基准数据。 |
| `guillemservera/sp500-nasdaq-spy-qqq-ohlcv-data` | S&P 500 and NASDAQ 100: Daily Data | 1,267,098 | 2,550 | 24 | <https://www.kaggle.com/datasets/guillemservera/sp500-nasdaq-spy-qqq-ohlcv-data> | S&P500 / 纳指 / SPY / QQQ OHLCV，用于基准复制与相对强弱对比。 |
| `guillemservera/vix-cboe-volatility-index-daily-updated` | VIX (CBOE Volatility Index) Daily Updated | 119,226 | 1,181 | 22 | <https://www.kaggle.com/datasets/guillemservera/vix-cboe-volatility-index-daily-updated> | VIX 日频数据，本策略波动率滤网与对冲时点判定的输入。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、Notebooks (Kernels)

| ref | 标题 | 作者 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `mburakergenc/applying-evaluating-a-momentum-trading-strategy` | Applying/Evaluating a Momentum Trading Strategy | Burak Ergenc | 29 | <https://www.kaggle.com/code/mburakergenc/applying-evaluating-a-momentum-trading-strategy> | 动量策略的实盘化实现与评估，对应本策略动量跟踪层。 |
| `shtrausslearning/building-an-asset-trading-strategy` | Building an Asset Trading Strategy | Andrey Shtrauss | 1,014 | <https://www.kaggle.com/code/shtrausslearning/building-an-asset-trading-strategy> | 从信号到交易策略的完整构建流程，可作工程骨架参考。 |
| `artemburenok/hedging-portfolio-with-options-greeks-var` | Hedging portfolio with options (greeks, VaR) | Artem Burenok | 43 | <https://www.kaggle.com/code/artemburenok/hedging-portfolio-with-options-greeks-var> | 含 Greeks 与 VaR 的期权对冲实现，直接对应 Delta-Gamma 对冲层。 |

拉取：`kaggle kernels pull <ref> -p notebooks/`

---

## 4、竞赛 (Competitions)

| ref | 奖励 | 队伍数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | :--- | :--- |
| `optiver-realized-volatility-prediction` | ? | ? | <https://www.kaggle.com/competitions/optiver-realized-volatility-prediction> | 已实现波动率预测竞赛，对应本策略波动率建模与对冲时点。 |

---

## 5、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
