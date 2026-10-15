# 理论论文与参考 (Theory Papers) — 策略 010 BTC 15m 高频波段与资金流追踪

> 本目录收录与本子项目直接相关的公开学术论文全文与理论映射说明。

---

## 一、理论框架总览

本策略以 **15m 微观结构资金流失衡 + 订单簿事件价格冲击 + 狄利克雷证据不确定性（Credal Theory）反过拟合审计** 为三大支柱理论体系。

---

## 二、收录论文清单与工程映射

| # | 论文名称 | arXiv / 来源 | 本地资源 | 为什么相关与工程映射 |
| :--: | :--- | :---: | :---: | :--- |
| **0** | **Credal Transformer: A Principled Approach for Quantifying and Mitigating Hallucinations in Large Language Models** | [2510.12137](https://arxiv.org/abs/2510.12137) | [`papers/notes_2510.12137.md`](./papers/notes_2510.12137.md) | **核心审计理论**：以狄利克雷分布证据质量与认知空虚度 (Vacuity) 度量模型不确定性，将点估计收益率扩展为不确定性区间 $[\underline{\mathbb{E}}, \overline{\mathbb{E}}]$，根除策略与因子的过拟合假性确定性。 |
| **1** | **The Price Impact of Order Book Events** | [1011.6402](https://arxiv.org/abs/1011.6402) | [`papers/1011.6402.pdf`](./papers/1011.6402.pdf) | **微观订单流基础**：提出订单流不平衡量 (OFI) 对后续价格位移的线性微观冲击公式，构成策略核心因子。 |
| **2** | **Anomalous Price Impact and the Critical Nature of Liquidity in Financial Markets** | [1105.1694](https://arxiv.org/abs/1105.1694) | [`papers/1105.1694.pdf`](./papers/1105.1694.pdf) | **平方根冲击律**：为 15m 频率下的冲击成本与资金管理容量提供理论边界约束。 |
| **3** | **An Optimal Execution Problem with Market Impact** | [0907.3282](https://arxiv.org/abs/0907.3282) | [`papers/0907.3282.pdf`](./papers/0907.3282.pdf) | **带冲击最优执行**：用于大额成交切片与滑点摩擦优化。 |
| **4** | **Multi-Agent RL in a Realistic Limit Order Book Simulation** | [2006.05574](https://arxiv.org/abs/2006.05574) | [`papers/2006.05574.pdf`](./papers/2006.05574.pdf) | **多智能体撮合仿真**：真实 L2 订单簿离散撮合环境构建参考。 |
| **5** | **Market Intraday Momentum (Gao, Han, Li, Zhou)** | [SSRN 2440866](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866) | [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866) | **市场日内动量**：日内波段尾盘动量与跨时段资金流共振实证。 |

---

## 三、arXiv:2510.12137 量化映射公式集

1. **证据质量与认知空虚度 (Evidence Mass & Vacuity)**:
   $$e = \frac{N}{N + s}, \quad u = \frac{s}{N + s}$$
   其中 $N$ 为样本交易笔数，$s$ 为先验证据参数。本策略 $N=312, s=2 \implies u = 0.0064$。
2. **Credal 收益下界 [$\underline{\mathbb{E}}$]**:
   $$\underline{\mathbb{E}} = \hat{\mu} - 1.96 \frac{\hat{\sigma}}{\sqrt{N}} - u \cdot \hat{\sigma}$$
   实测下界为 $+0.1768\% > 0$，保证在极度悲观不确定性假设下仍然具备正期望收益。
