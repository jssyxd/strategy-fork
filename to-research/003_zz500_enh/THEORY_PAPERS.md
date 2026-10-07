# 理论论文与参考 (Theory Papers) — 策略 003 中证 500 指数增强

> 本目录 `papers/` 收录与该子项目直接相关的公开论文全文（arXiv 开放获取 PDF），并附 SSRN / DOI 链接。每篇论文均给出「为什么相关」的说明。

---

## 一、总体说明

本策略 = 自动因子挖掘（符号/强化学习）+ 因子在线聚合（乘法权重）+ 树模型底座 + 指数增强约束。

---

## 二、arXiv 论文（全文 PDF 已随目录提供）

| # | 论文 | arXiv | 本地文件 | 为什么相关 |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **QuantFactor REINFORCE: Mining Steady Formulaic Alpha Factors** | [2409.05144](https://arxiv.org/abs/2409.05144) | [`2409.05144.pdf`](./papers/2409.05144.pdf) | 用方差约束的 REINFORCE 稳定挖掘公式化 Alpha 因子，对应本策略「自动因子挖掘 + 稳定性约束」。 |
| 2 | **AlphaForge: Mining and Dynamically Combining Formulaic Alpha Factors** | [2406.18394](https://arxiv.org/abs/2406.18394) | [`2406.18394.pdf`](./papers/2406.18394.pdf) | AlphaForge：挖掘并动态组合公式化因子的完整框架，对应因子库生成与动态组合。 |
| 3 | **Synergistic Formulaic Alpha Generation via Reinforcement Learning** | [2401.02710](https://arxiv.org/abs/2401.02710) | [`2401.02710.pdf`](./papers/2401.02710.pdf) | 强化学习生成协同（低相关）公式化 Alpha 集合，对应本策略对因子低相关性的追求。 |
| 4 | **XGBoost: A Scalable Tree Boosting System** | [1603.02754](https://arxiv.org/abs/1603.02754) | [`1603.02754.pdf`](./papers/1603.02754.pdf) | XGBoost，本策略多因子非线性底座（LightGBM 同源梯度提升树）的算法基础。 |

---

## 三、SSRN / DOI 论文（链接）

> 说明：SSRN 对自动化访问启用了 Cloudflare 校验，本环境**无法抓取其正文 PDF**，故此处提供**官方链接 + 相关性说明**。链接与编号已通过 Crossref（DOI `10.2139/ssrn.*`）核对。

| # | 论文 | 链接 | 为什么相关 |
| :--: | :--- | :--- | :--- |
| 1 | **Building Diversified Portfolios that Outperform Out-of-Sample (López de Prado)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678> | 指数增强中的权重分配与风险预算参考。 |
| 2 | **The Deflated Sharpe Ratio (Bailey, López de Prado)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551> | 因子挖掘场景下大量候选带来的选择偏差校正，直接用于本策略的因子入池门槛。 |

---

## 四、获取与引用约定

- arXiv 论文为开放获取，`papers/*.pdf` 为对应 arXiv 版本的全文副本；引用请以 arXiv 编号为准。
- SSRN 论文正文受站点防护限制未能随目录提供，请通过上表链接访问。
- 本目录仅用于技术研究与复现参考，版权归原作者所有。
