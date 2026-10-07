# Kaggle 关联资源 (Kaggle Resources) — 策略 003 中证 500 指数增强

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`alpha factor`、`quant factor`、`formulaic alpha`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `waelelghazzawi/quantitative-alpha-factor-feature-store-for-ml` | Quantitative Alpha Factor Feature Store for ML | 0 | 1 | 0 | <https://www.kaggle.com/datasets/waelelghazzawi/quantitative-alpha-factor-feature-store-for-ml> | Alpha 因子特征库，对应本策略因子挖掘后的因子池存储与筛选。 |
| `unnatisolutions/unnat-alpha-signals-india-nse-equities` | unnatisolutions/unnat-alpha-signals-india-nse-equities | ? | ? | ? | <https://www.kaggle.com/datasets/unnatisolutions/unnat-alpha-signals-india-nse-equities> | 已计算的 Alpha 信号面板，可作指数增强输入端口的现成样例。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、Notebooks (Kernels)

| ref | 标题 | 作者 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `kamalnaithani/lightgbm-stock-prediction-1-1` | LightGBM Stock Prediction 1.1   | Kamal | 225 | <https://www.kaggle.com/code/kamalnaithani/lightgbm-stock-prediction-1-1> | LightGBM 选股/预测流程，对应本策略的树模型底座。 |

拉取：`kaggle kernels pull <ref> -p notebooks/`

---

## 4、竞赛 (Competitions)

| ref | 奖励 | 队伍数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | :--- | :--- |
| `jpx-tokyo-stock-exchange-prediction` | ? | ? | <https://www.kaggle.com/competitions/jpx-tokyo-stock-exchange-prediction> | 指数增强类竞赛的基准任务与评估（含 Sharpe / Rank IC）。 |
| `optiver-trading-at-the-close` | ? | ? | <https://www.kaggle.com/competitions/optiver-trading-at-the-close> | 收盘价预测竞赛，对应指数增强的微观执行与收盘撮合问题。 |

---

## 5、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
