# 理论论文与参考 (Theory Papers) — 策略 005 可转债 CTA（低容量高夏普）

> 本目录 `papers/` 收录与该子项目直接相关的公开论文全文（arXiv 开放获取 PDF），并附 SSRN / DOI 链接。每篇论文均给出「为什么相关」的说明。

---

## 一、总体说明

本策略 = 双低（价格+转股溢价率）底仓 + CTA 趋势择时 + 平方根冲击模型测算容量。

---

## 二、arXiv 论文（全文 PDF 已随目录提供）

| # | 论文 | arXiv | 本地文件 | 为什么相关 |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **Binomial-Tree Approach to Convertible Bond Pricing** | [1111.2683](https://arxiv.org/abs/1111.2683) | [`1111.2683.pdf`](./papers/1111.2683.pdf) | 可转债二叉树定价的关键分析，双低因子与债底价值计算的理论基础。 |
| 2 | **Enhancing Time Series Momentum Strategies Using Deep Neural Networks** | [1904.04912](https://arxiv.org/abs/1904.04912) | [`1904.04912.pdf`](./papers/1904.04912.pdf) | 深度学习动量跟踪，用于本策略 CTA 趋势择时层。 |
| 3 | **Anomalous Price Impact and the Critical Nature of Liquidity in Financial Markets** | [1105.1694](https://arxiv.org/abs/1105.1694) | [`1105.1694.pdf`](./papers/1105.1694.pdf) | 平方根市场冲击律（流动性临界性），直接支撑本策略「平方根冲击模型测算容量上限」的结论。 |

---

## 三、SSRN / DOI 论文（链接）

> 说明：SSRN 对自动化访问启用了 Cloudflare 校验，本环境**无法抓取其正文 PDF**，故此处提供**官方链接 + 相关性说明**。链接与编号已通过 Crossref（DOI `10.2139/ssrn.*`）核对。

| # | 论文 | 链接 | 为什么相关 |
| :--: | :--- | :--- | :--- |
| 1 | **Simulating Convertible Bond Arbitrage Portfolios** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1636159> | 可转债套利组合的模拟研究，双低轮动与套利收益结构的实证参考。 |
| 2 | **Time Series Momentum (Moskowitz, Ooi, Pedersen)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463> | 趋势择时（TSMOM）的原始文献，CTA 层的基准方法。 |

---

## 四、获取与引用约定

- arXiv 论文为开放获取，`papers/*.pdf` 为对应 arXiv 版本的全文副本；引用请以 arXiv 编号为准。
- SSRN 论文正文受站点防护限制未能随目录提供，请通过上表链接访问。
- 本目录仅用于技术研究与复现参考，版权归原作者所有。
