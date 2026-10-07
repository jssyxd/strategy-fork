# 理论论文与参考 (Theory Papers) — 策略 011 深度学习期权做市与 Delta-Gamma 对冲

> 本目录 `papers/` 收录与该子项目直接相关的公开论文全文（arXiv 开放获取 PDF），并附 SSRN / DOI 链接。每篇论文均给出「为什么相关」的说明。

---

## 一、总体说明

本策略 = 多任务波动率/相关性/CVaR 预测网络 + 深度对冲优化器 + 期权多腿状态机 + 筹码微观结构。

---

## 二、arXiv 论文（全文 PDF 已随目录提供）

| # | 论文 | arXiv | 本地文件 | 为什么相关 |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **Deep Hedging** | [1802.03042](https://arxiv.org/abs/1802.03042) | [`1802.03042.pdf`](./papers/1802.03042.pdf) | Deep Hedging 原始论文，本策略对冲优化器的方法论核心。 |
| 2 | **Attention Is All You Need** | [1706.03762](https://arxiv.org/abs/1706.03762) | [`1706.03762.pdf`](./papers/1706.03762.pdf) | 注意力架构，本策略多任务预测网络的骨干。 |
| 3 | **Option Market Making with Hedging-Induced Market Impact** | [2511.02518](https://arxiv.org/abs/2511.02518) | [`2511.02518.pdf`](./papers/2511.02518.pdf) | 考虑对冲冲击的期权做市模型，支撑本策略对交易成本的显式惩罚项。 |
| 4 | **An Approximate Solution for Options Market-Making in High Dimension** | [2009.00907](https://arxiv.org/abs/2009.00907) | [`2009.00907.pdf`](./papers/2009.00907.pdf) | 高维期权做市近似解，为多维对冲提供可解析的对照基线。 |
| 5 | **FlashAttention: Fast and Memory-Efficient Exact Attention** | [2205.14135](https://arxiv.org/abs/2205.14135) | [`2205.14135.pdf`](./papers/2205.14135.pdf) | FlashAttention 的 IO 感知精确注意力，是本策略高频推理加速的工程参考。 |

---

## 四、获取与引用约定

- arXiv 论文为开放获取，`papers/*.pdf` 为对应 arXiv 版本的全文副本；引用请以 arXiv 编号为准。
- SSRN 论文正文受站点防护限制未能随目录提供，请通过上表链接访问。
- 本目录仅用于技术研究与复现参考，版权归原作者所有。
