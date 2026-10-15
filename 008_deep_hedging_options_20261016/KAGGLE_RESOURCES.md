# Kaggle 关联资源 (Kaggle Resources) — 策略 011 深度学习期权做市与 Delta-Gamma 对冲

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`options chain data`、`volatility index`、`deep hedging`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `guillemservera/vix-cboe-volatility-index-daily-updated` | VIX (CBOE Volatility Index) Daily Updated | 119,226 | 1,181 | 22 | <https://www.kaggle.com/datasets/guillemservera/vix-cboe-volatility-index-daily-updated> | VIX 日频数据，对冲状态与波动率环境的输入。 |
| `jonathanbesomi/cboe-volatility-index-vix` | CBOE Volatility Index (^VIX) | 108,341 | 303 | 11 | <https://www.kaggle.com/datasets/jonathanbesomi/cboe-volatility-index-vix> | CBOE VIX 历史，作为波动率预测的标签/基准。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、Notebooks (Kernels)

| ref | 标题 | 作者 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `marimbino/deep-hedging` | Deep Hedging | Marimbino | 3 | <https://www.kaggle.com/code/marimbino/deep-hedging> | Deep Hedging 实现，与本策略的对冲优化器层直接对应。 |

拉取：`kaggle kernels pull <ref> -p notebooks/`

---

## 4、竞赛 (Competitions)

| ref | 奖励 | 队伍数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | :--- | :--- |
| `optiver-realized-volatility-prediction` | ? | ? | <https://www.kaggle.com/competitions/optiver-realized-volatility-prediction> | 已实现波动率预测竞赛。 |
| `optiver-trading-at-the-close` | ? | ? | <https://www.kaggle.com/competitions/optiver-trading-at-the-close> | 收盘交易竞赛，对应期权/标的的微观执行与成本控制。 |

---

## 5、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
