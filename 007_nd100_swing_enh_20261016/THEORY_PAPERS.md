# 理论论文与参考 (Theory Papers) — 策略 004 纳斯达克 100 ETF 增强

> 本目录 `papers/` 收录与该子项目直接相关的公开论文全文（arXiv 开放获取 PDF），并附 SSRN / DOI 链接。每篇论文均给出「为什么相关」的说明。

---

## 一、总体说明

本策略 = 动量跟踪（时序动量 / 深度学习动量）+ Delta-Gamma 期权对冲增强。

---

## 二、arXiv 论文（全文 PDF 已随目录提供）

| # | 论文 | arXiv | 本地文件 | 为什么相关 |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **Enhancing Time Series Momentum Strategies Using Deep Neural Networks** | [1904.04912](https://arxiv.org/abs/1904.04912) | [`1904.04912.pdf`](./papers/1904.04912.pdf) | 用深度网络增强时序动量策略，是本策略动量跟踪层的直接方法论来源。 |
| 2 | **Deep Hedging** | [1802.03042](https://arxiv.org/abs/1802.03042) | [`1802.03042.pdf`](./papers/1802.03042.pdf) | 深度对冲 (Deep Hedging) 原始论文：以神经网络直接学习对冲策略而非解析希腊字母，对应本策略的学习型对冲层。 |
| 3 | **Option Market Making with Hedging-Induced Market Impact** | [2511.02518](https://arxiv.org/abs/2511.02518) | [`2511.02518.pdf`](./papers/2511.02518.pdf) | 考虑对冲引致市场冲击的期权做市模型，用于评估 Delta-Gamma 对冲带来的冲击成本。 |
| 4 | **An Approximate Solution for Options Market-Making in High Dimension** | [2009.00907](https://arxiv.org/abs/2009.00907) | [`2009.00907.pdf`](./papers/2009.00907.pdf) | 高维期权做市的近似解法，为多腿对冲的维度灾难提供近似求解思路。 |

---

## 三、SSRN / DOI 论文（链接）

> 说明：SSRN 对自动化访问启用了 Cloudflare 校验，本环境**无法抓取其正文 PDF**，故此处提供**官方链接 + 相关性说明**。链接与编号已通过 Crossref（DOI `10.2139/ssrn.*`）核对。

| # | 论文 | 链接 | 为什么相关 |
| :--: | :--- | :--- | :--- |
| 1 | **Time Series Momentum (Moskowitz, Ooi, Pedersen)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463> | 时序动量 (TSMOM) 原始论文，本策略动量端的理论与基准。 |

---

## 四、获取与引用约定

- arXiv 论文为开放获取，`papers/*.pdf` 为对应 arXiv 版本的全文副本；引用请以 arXiv 编号为准。
- SSRN 论文正文受站点防护限制未能随目录提供，请通过上表链接访问。
- 本目录仅用于技术研究与复现参考，版权归原作者所有。
