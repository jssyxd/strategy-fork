# 理论论文与参考 (Theory Papers) — 策略 002 A 股全市场截面选股

> 本目录 `papers/` 收录与该子项目直接相关的公开论文全文（arXiv 开放获取 PDF），并附 SSRN / DOI 链接。每篇论文均给出「为什么相关」的说明。

---

## 一、总体说明

本策略 = 端到端 Transformer 截面建模 + 低秩衰减正则 + 公式化因子库。以下论文对应注意力架构、低秩正则与公式化 Alpha 三个关键点。

---

## 二、arXiv 论文（全文 PDF 已随目录提供）

| # | 论文 | arXiv | 本地文件 | 为什么相关 |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **Attention Is All You Need** | [1706.03762](https://arxiv.org/abs/1706.03762) | [`1706.03762.pdf`](./papers/1706.03762.pdf) | Transformer 原论文，本策略截面时序注意力骨干的直接来源。 |
| 2 | **Low-Rank Bottleneck in Multi-Head Attention** | [2002.07028](https://arxiv.org/abs/2002.07028) | [`2002.07028.pdf`](./papers/2002.07028.pdf) | 揭示多头注意力的低秩瓶颈并给出低秩正则方案，是本策略 Low-rank Decay 正则的理论依据。 |
| 3 | **Neural Collapse Under MSE Loss** | [2106.02073](https://arxiv.org/abs/2106.02073) | [`2106.02073.pdf`](./papers/2106.02073.pdf) | 神经坍缩（Neural Collapse）在 MSE 损失下的动力学分析，解释深层分类/回归表示为何趋向低秩，为低秩衰减提供机理支撑。 |
| 4 | **101 Formulaic Alphas** | [1601.00991](https://arxiv.org/abs/1601.00991) | [`1601.00991.pdf`](./papers/1601.00991.pdf) | 101 个公式化 Alpha 因子，本策略因子库的经典范本。 |

---

## 三、SSRN / DOI 论文（链接）

> 说明：SSRN 对自动化访问启用了 Cloudflare 校验，本环境**无法抓取其正文 PDF**，故此处提供**官方链接 + 相关性说明**。链接与编号已通过 Crossref（DOI `10.2139/ssrn.*`）核对。

| # | 论文 | 链接 | 为什么相关 |
| :--: | :--- | :--- | :--- |
| 1 | **…and the Cross-Section of Expected Returns (Harvey, Liu, Zhu)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2249314> | 对已发表「因子」的大规模多重检验复核：警示截面因子易被过拟合，是本策略因子筛选与显著性检验的方法论基础。 |
| 2 | **The Deflated Sharpe Ratio (Bailey, López de Prado)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551> | 回测过拟合校正，用于截面策略的样本外评估。 |

---

## 四、获取与引用约定

- arXiv 论文为开放获取，`papers/*.pdf` 为对应 arXiv 版本的全文副本；引用请以 arXiv 编号为准。
- SSRN 论文正文受站点防护限制未能随目录提供，请通过上表链接访问。
- 本目录仅用于技术研究与复现参考，版权归原作者所有。
