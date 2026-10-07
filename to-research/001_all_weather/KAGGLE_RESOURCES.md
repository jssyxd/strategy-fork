# Kaggle 关联资源 (Kaggle Resources) — 策略 001 全天候 (All-Weather)

> 与同目录 `THEORY_PAPERS.md`（理论论文）并列：本文件汇总 **Kaggle 平台上可复用的数据集 / Notebook / 竞赛**，用于该子项目的深入复现与实验对照。

> 检索时间：2026-10-08 · 工具：Kaggle CLI 2.2.4（`kaggle datasets list -s` / `kaggle kernels list -s` / `kaggle competitions list -s`）。

---

## 一、检索词

`portfolio optimization`、`risk parity portfolio`、`multi asset allocation`、`macroeconomic indicators`

---

## 2、数据集 (Datasets)

| ref | 标题 | 规模(B) | 下载量 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| `waelelghazzawi/multi-asset-risk-parity-hrp` | Multi-Asset Risk Parity & Hierarchical Risk Parity | 730,180 | 6 | 0 | <https://www.kaggle.com/datasets/waelelghazzawi/multi-asset-risk-parity-hrp> | 多资产风险平价 / 分层风险平价 (HRP) 数据集，直接对应本策略 ERC/HRP 权重求解与对照实验。 |
| `waelelghazzawi/multi-asset-etf-returns-factor-benchmarks` | Multi-Asset ETF Daily Returns & Factor Benchmarks | 476,796 | 25 | 0 | <https://www.kaggle.com/datasets/waelelghazzawi/multi-asset-etf-returns-factor-benchmarks> | 多资产 ETF 日收益 + 因子基准，可作全天候多资产组合的收益率面板与风格基准。 |
| `tanishksharma9905/global-economic-indicators-20102025` | Global Economic Indicators (2010–2025)- World bank | 263,193 | 6,770 | 56 | <https://www.kaggle.com/datasets/tanishksharma9905/global-economic-indicators-20102025> | 世界银行口径的全球经济指标，用于宏观增长/通胀四象限打分的输入变量。 |
| `federalreserve/interest-rates` | Federal Reserve Interest Rates, 1954-Present | 7,069 | 11,434 | 178 | <https://www.kaggle.com/datasets/federalreserve/interest-rates> | 美联储利率长历史序列，用于利率周期与久期资产（长债）判定。 |

下载：`kaggle datasets download -d <ref> -p data/ --unzip`

---

## 3、Notebooks (Kernels)

| ref | 标题 | 作者 | 票数 | 链接 | 为什么相关 |
| :--- | :--- | :--- | ---: | :--- | :--- |
| `alenavorushilova/fin-analysis-portfolio-allocation-optimization` | Fin Analysis-Portfolio Allocation Optimization | voru588 | 101 | <https://www.kaggle.com/code/alenavorushilova/fin-analysis-portfolio-allocation-optimization> | 组合分配优化的完整实操 Notebook，可对照本策略优化器实现。 |
| `yousefsaeedian/portfolio-optimization-in-practice` | Portfolio Optimization in practice 🧮 | Yousef Saeedian | 93 | <https://www.kaggle.com/code/yousefsaeedian/portfolio-optimization-in-practice> | 组合优化实践（Markowitz → 实务约束），权重求解的工程参考。 |
| `lorenzopardini/all-weather-contrarian-alpha-portfolio-optimizer` | All-Weather Contrarian Alpha — Portfolio Optimizer | Lorenzo Pardini | 6 | <https://www.kaggle.com/code/lorenzopardini/all-weather-contrarian-alpha-portfolio-optimizer> | 全天候 + 反向 Alpha 的组合优化器实现，与本策略「周期判定 + 风险预算」结构最接近。 |

拉取：`kaggle kernels pull <ref> -p notebooks/`

---

## 4、使用与注意

- 上表 `ref` 可直接用于对应 CLI：`kaggle datasets download -d <ref>`、`kaggle kernels pull <ref>`、`kaggle competitions download -c <ref>`。
- Kaggle 资源为社区上传，**许可与数据口径各异**，使用前请核对各自页面的 License 与字段说明。
- 本文件仅为检索索引，不代下载；如需落盘到本目录 `data/`，请自行执行命令并遵守其许可。
