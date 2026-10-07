# 理论论文与参考 (Theory Papers) — 策略 010 BTC 15m 高频波段与资金流追踪

> 本目录 `papers/` 收录与该子项目直接相关的公开论文全文（arXiv 开放获取 PDF），并附 SSRN / DOI 链接。每篇论文均给出「为什么相关」的说明。

---

## 一、总体说明

本策略 = 15m 波段动量 + 资金流/订单流监控 + 基准相对强弱。

---

## 二、arXiv 论文（全文 PDF 已随目录提供）

| # | 论文 | arXiv | 本地文件 | 为什么相关 |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **The Price Impact of Order Book Events** | [1011.6402](https://arxiv.org/abs/1011.6402) | [`1011.6402.pdf`](./papers/1011.6402.pdf) | 订单簿事件价格冲击，为本策略资金流突变信号提供微观结构基础。 |
| 2 | **Anomalous Price Impact and the Critical Nature of Liquidity in Financial Markets** | [1105.1694](https://arxiv.org/abs/1105.1694) | [`1105.1694.pdf`](./papers/1105.1694.pdf) | 平方根冲击律，用于 15m 频率的冲击与容量估计。 |
| 3 | **An Optimal Execution Problem with Market Impact** | [0907.3282](https://arxiv.org/abs/0907.3282) | [`0907.3282.pdf`](./papers/0907.3282.pdf) | 带冲击的最优执行，用于波段交易的执行成本建模。 |
| 4 | **Multi-Agent RL in a Realistic Limit Order Book Simulation** | [2006.05574](https://arxiv.org/abs/2006.05574) | [`2006.05574.pdf`](./papers/2006.05574.pdf) | 真实订单簿多智能体仿真环境，可作为本策略高频回测的撮合仿真参考。 |

---

## 三、SSRN / DOI 论文（链接）

> 说明：SSRN 对自动化访问启用了 Cloudflare 校验，本环境**无法抓取其正文 PDF**，故此处提供**官方链接 + 相关性说明**。链接与编号已通过 Crossref（DOI `10.2139/ssrn.*`）核对。

| # | 论文 | 链接 | 为什么相关 |
| :--: | :--- | :--- | :--- |
| 1 | **Market Intraday Momentum (Gao, Han, Li, Zhou)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866> | 市场日内动量（尾盘动量）实证，本策略日内波段动量的理论对照。 |

---

## 四、获取与引用约定

- arXiv 论文为开放获取，`papers/*.pdf` 为对应 arXiv 版本的全文副本；引用请以 arXiv 编号为准。
- SSRN 论文正文受站点防护限制未能随目录提供，请通过上表链接访问。
- 本目录仅用于技术研究与复现参考，版权归原作者所有。
