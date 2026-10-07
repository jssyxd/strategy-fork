# Kaggle 关联资源 (Kaggle Resources) — 策略 007 商品期货 CTA

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`commodity futures prices`、`futures term structure`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `waelelghazzawi/commodity-futures-term-structure-roll-yields` | Commodity Futures Term Structure & Roll Yields | 812,210 | 31 | 0 | <https://www.kaggle.com/datasets/waelelghazzawi/commodity-futures-term-structure-roll-yields> | 商品期货期限结构与展期收益率 (Roll Yield)，与本策略 carry/期限结构因子完全对应。 |
| `mattiuzc/commodity-futures-price-history` | Commodity Futures Price History | 1,846,642 | 1,899 | 26 | <https://www.kaggle.com/datasets/mattiuzc/commodity-futures-price-history> | 主流商品期货长历史价格，多品种时序动量与跨期套利的数据基础。 |
| `guillemservera/fuels-futures-data` | Oil, Gas & Other Fuels Futures Data | 1,268,927 | 5,883 | 65 | <https://www.kaggle.com/datasets/guillemservera/fuels-futures-data> | 能源类期货数据，用于能化板块的期限结构与动量研究。 |
| `guillemservera/precious-metals-data` | Gold, Silver & Precious Metals Futures Daily Data | 825,788 | 5,110 | 52 | <https://www.kaggle.com/datasets/guillemservera/precious-metals-data> | 贵金属期货数据，补充金属板块截面。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、竞赛 (Competitions)

| ref | 奖励 | 队伍数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | :--- | :--- |
| `mitsui-commodity-prediction-challenge` | ? | ? | <https://www.kaggle.com/competitions/mitsui-commodity-prediction-challenge> | 商品价格预测竞赛，对应本策略多品种时序预测的评估口径。 |

---

## 4、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
