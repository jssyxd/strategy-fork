# 理论论文与参考 (Theory Papers) — 策略 009 ETH 波动率挤压 (Vol Squeeze)

> 本目录 `papers/` 收录与该子项目直接相关的公开论文全文（arXiv 开放获取 PDF），并附 SSRN / DOI 链接。每篇论文均给出「为什么相关」的说明。

---

## 一、总体说明

本策略 = 隐含波动率曲面建模 (SVI) + IV/RV 偏离套利 + 期权多腿状态机 + 可解释定价。

---

## 二、arXiv 论文（全文 PDF 已随目录提供）

| # | 论文 | arXiv | 本地文件 | 为什么相关 |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **Arbitrage-Free SVI Volatility Surfaces** | [1204.0646](https://arxiv.org/abs/1204.0646) | [`1204.0646.pdf`](./papers/1204.0646.pdf) | 无套利 SVI 波动率曲面参数化，本策略 IV 曲面建模的数学基础。 |
| 2 | **Volatility Is Rough** | [1410.3394](https://arxiv.org/abs/1410.3394) | [`1410.3394.pdf`](./papers/1410.3394.pdf) | 粗糙波动率（Volatility is Rough），解释 IV 长期记忆与 RV 预测的统计特征。 |
| 3 | **Physics-Informed Neural Network for Option Pricing** | [2312.06711](https://arxiv.org/abs/2312.06711) | [`2312.06711.pdf`](./papers/2312.06711.pdf) | PINN 期权定价，本策略可解释定价组件的候选实现。 |
| 4 | **Sparse Autoencoders Find Highly Interpretable Features in Language Models** | [2309.08600](https://arxiv.org/abs/2309.08600) | [`2309.08600.pdf`](./papers/2309.08600.pdf) | 稀疏自编码器提取可解释特征，对应本策略将定价格式网络隐层解耦为可读的希腊字母/曲面特征。 |
| 5 | **Option Market Making with Hedging-Induced Market Impact** | [2511.02518](https://arxiv.org/abs/2511.02518) | [`2511.02518.pdf`](./papers/2511.02518.pdf) | 含对冲冲击的期权做市，评估多腿组合的冲击成本与容量。 |

---

## 四、获取与引用约定

- arXiv 论文为开放获取，`papers/*.pdf` 为对应 arXiv 版本的全文副本；引用请以 arXiv 编号为准。
- SSRN 论文正文受站点防护限制未能随目录提供，请通过上表链接访问。
- 本目录仅用于技术研究与复现参考，版权归原作者所有。
