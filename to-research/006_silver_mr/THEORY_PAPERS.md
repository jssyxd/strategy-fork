# 理论论文与参考 (Theory Papers) — 策略 006 白银均值回归 SMR

> 本目录 `papers/` 收录与该子项目直接相关的公开论文全文（arXiv 开放获取 PDF），并附 SSRN / DOI 链接。每篇论文均给出「为什么相关」的说明。

---

## 一、总体说明

本策略 = 做市商最优控制（库存风险）+ 高频微观结构 + 在线蒸馏克服样本稀疏。

---

## 二、arXiv 论文（全文 PDF 已随目录提供）

| # | 论文 | arXiv | 本地文件 | 为什么相关 |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **Dealing with the Inventory Risk: A Solution to the Market Making Problem** | [1105.3115](https://arxiv.org/abs/1105.3115) | [`1105.3115.pdf`](./papers/1105.3115.pdf) | Avellaneda-Stoikov 做市问题的严格解（库存风险定价、保留价格与最优价差），是本策略保留价格与动态价差公式的直接来源。 |
| 2 | **The Price Impact of Order Book Events** | [1011.6402](https://arxiv.org/abs/1011.6402) | [`1011.6402.pdf`](./papers/1011.6402.pdf) | 订单簿事件的价格冲击实证，给出高频做市所需的微观结构冲击度量。 |
| 3 | **Anomalous Price Impact and the Critical Nature of Liquidity in Financial Markets** | [1105.1694](https://arxiv.org/abs/1105.1694) | [`1105.1694.pdf`](./papers/1105.1694.pdf) | 平方根冲击律与流动性临界性，用于高频信号容量与冲击估计。 |
| 4 | **Self-Distillation Amplifies Regularization in Hilbert Space** | [2002.05715](https://arxiv.org/abs/2002.05715) | [`2002.05715.pdf`](./papers/2002.05715.pdf) | 自蒸馏的正则化机理，是本策略「在线蒸馏 + 数据合成克服样本稀疏」的理论依托。 |
| 5 | **Deep RL for Market Making under a Hawkes Process LOB** | [2207.09951](https://arxiv.org/abs/2207.09951) | [`2207.09951.pdf`](./papers/2207.09951.pdf) | Hawkes 过程订单簿下的深度强化学习做市，可作为本策略做市参数自适应升级的参考。 |

---

## 四、获取与引用约定

- arXiv 论文为开放获取，`papers/*.pdf` 为对应 arXiv 版本的全文副本；引用请以 arXiv 编号为准。
- SSRN 论文正文受站点防护限制未能随目录提供，请通过上表链接访问。
- 本目录仅用于技术研究与复现参考，版权归原作者所有。
