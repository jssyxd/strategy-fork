# 理论论文与参考 (Theory Papers) — 策略 007 商品期货 CTA

> 本目录 `papers/` 收录与该子项目直接相关的公开论文全文（arXiv 开放获取 PDF），并附 SSRN / DOI 链接。每篇论文均给出「为什么相关」的说明。

---

## 一、总体说明

本策略 = 期限结构展期收益 (carry/roll yield) + 时序动量 + 宏观基本面因子 + 树模型 + 跨品种风险配置。

---

## 二、arXiv 论文（全文 PDF 已随目录提供）

| # | 论文 | arXiv | 本地文件 | 为什么相关 |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **Enhancing Time Series Momentum Strategies Using Deep Neural Networks** | [1904.04912](https://arxiv.org/abs/1904.04912) | [`1904.04912.pdf`](./papers/1904.04912.pdf) | 深度学习时序动量，用于本策略多品种动量端。 |
| 2 | **A Comparative Study of Hierarchical Risk Parity and Eigen Portfolios** | [2210.00984](https://arxiv.org/abs/2210.00984) | [`2210.00984.pdf`](./papers/2210.00984.pdf) | HRP 与特征组合对比，对应本策略跨品种层次风险平价配置。 |
| 3 | **XGBoost: A Scalable Tree Boosting System** | [1603.02754](https://arxiv.org/abs/1603.02754) | [`1603.02754.pdf`](./papers/1603.02754.pdf) | XGBoost，本策略多品种时序预测的底座模型。 |
| 4 | **An Optimal Execution Problem with Market Impact** | [0907.3282](https://arxiv.org/abs/0907.3282) | [`0907.3282.pdf`](./papers/0907.3282.pdf) | 带市场冲击的最优执行问题，用于商品合约下单与冲击成本建模。 |

---

## 三、SSRN / DOI 论文（链接）

> 说明：SSRN 对自动化访问启用了 Cloudflare 校验，本环境**无法抓取其正文 PDF**，故此处提供**官方链接 + 相关性说明**。链接与编号已通过 Crossref（DOI `10.2139/ssrn.*`）核对。

| # | 论文 | 链接 | 为什么相关 |
| :--: | :--- | :--- | :--- |
| 1 | **Carry (Koijen, Moskowitz, Pedersen, Vrugt)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2298565> | Carry（含商品展期收益）的经典文献，本策略期限结构因子的原始理论。 |
| 2 | **Time Series Momentum (Moskowitz, Ooi, Pedersen)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463> | 时序动量原始论文，商品趋势端基准。 |

---

## 四、获取与引用约定

- arXiv 论文为开放获取，`papers/*.pdf` 为对应 arXiv 版本的全文副本；引用请以 arXiv 编号为准。
- SSRN 论文正文受站点防护限制未能随目录提供，请通过上表链接访问。
- 本目录仅用于技术研究与复现参考，版权归原作者所有。
