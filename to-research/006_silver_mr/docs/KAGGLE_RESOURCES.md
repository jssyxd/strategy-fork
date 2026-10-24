# Kaggle 关联资源 (Kaggle Resources) — 策略 006 白银均值回归 SMR

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`limit order book`、`silver futures`、`market making`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `martinsn/high-frequency-crypto-limit-order-book-data` | High Frequency Crypto Limit Order Book Data | 1,041,602,262 | 5,715 | 44 | <https://www.kaggle.com/datasets/martinsn/high-frequency-crypto-limit-order-book-data> | 高频 LOB 逐档数据，是本策略做市/均值回归高频回测的核心数据。 |
| `siavashraz/bitcoin-perpetualbtcusdtp-limit-order-book-data` | Bitcoin Limit Order Book (LOB) Data | 170,418,074 | 1,257 | 9 | <https://www.kaggle.com/datasets/siavashraz/bitcoin-perpetualbtcusdtp-limit-order-book-data> | 永续合约 LOB 数据，用于盘口库存与价差建模。 |
| `sergionefedov/synthetic-limit-order-book-market-microstructure` | Limit Order Book 10 days · 3 market regimes  | 16,204,538 | 33 | 2 | <https://www.kaggle.com/datasets/sergionefedov/synthetic-limit-order-book-market-microstructure> | 含三种市场状态的合成 LOB（可复现），适合做市参数在不同波动状态下的压力测试。 |
| `guillemservera/precious-metals-data` | Gold, Silver & Precious Metals Futures Daily Data | 825,788 | 5,110 | 52 | <https://www.kaggle.com/datasets/guillemservera/precious-metals-data> | 金银等贵金属期货日频数据，对应白银标的的宏观与期限结构背景。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、Notebooks (Kernels)

| ref | 标题 | 作者 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `anshumandey2103/avellaneda-stoikov-engine` | Avellaneda Stoikov Engine | Anshuman_Dey_9505 | 0 | <https://www.kaggle.com/code/anshumandey2103/avellaneda-stoikov-engine> | Avellaneda-Stoikov 做市引擎实现，与本策略保留价格/最优价差公式直接对应。 |
| `karandeepsinghsodhi/lab-06-avellaneda-stoikov-rl-execution` | Lab 06: Avellaneda-Stoikov & RL Execution | Karandeep Singh Sodhi | 0 | <https://www.kaggle.com/code/karandeepsinghsodhi/lab-06-avellaneda-stoikov-rl-execution> | A-S 模型 + 强化学习执行实验，可作为本策略参数自适应的升级参考。 |

拉取：`kaggle kernels pull <ref> -p notebooks/`

---

## 4、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
