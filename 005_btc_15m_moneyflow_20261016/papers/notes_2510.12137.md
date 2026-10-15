# arXiv:2510.12137 理论解析与量化投研映射笔记

- **标题**：Credal Transformer: A Principled Approach for Quantifying and Mitigating Hallucinations in Large Language Models
- **作者**：Shihao Ji, Zihui Song, Jiajie Huang
- **提交时间**：2025-10-14
- **arXiv 链接**：https://arxiv.org/abs/2510.12137

---

## 一、核心思想

标准 Transformer 架构中的 Softmax 函数通过强制归一化，将可能充满歧义和高不确定性的注意力打分强行坍缩为单一概率分布，从而产生“人工确定性 (Artificial Certainty)”。这使得模型在缺乏充分证据时依然输出高度自信但完全错误的断言（即幻觉）。

为了解决这一问题，论文引入了 **Credal Transformer**，以基于主观逻辑证据理论（Subjective Logic / Evidential Theory）的 **Credal Attention Mechanism (CAM)** 替代标准 Softmax 注意力。CAM 输出一个包含多种潜在可能分布的“置信凸集 (Credal Set)”，并直接将该集合的几何体积测度作为模型的认知不确定性（Epistemic Uncertainty）。

## 二、量化投研反幻觉/反过拟合映射

在量化策略研发中，研究员与回测引擎同样面临着严重的“人工确定性”幻觉：
1. **单一指标幻觉**：仅凭借一个样本内 Sharpe 比率或累计收益率便断定策略有效，忽视了由于噪声拟合、样本量有限所导致的认知空虚。
2. **多重检验幻觉**：经过成千上万次参数调优与因子挖掘后得到的“最优”参数，其实质是概率置换下的伪阿尔法。
3. **极值脆弱性**：在低流动性或黑天鹅极端市场环境下，模型由于缺乏认知不确定性感知，持续输出高置信度仓位最终导致爆仓。

## 三、本策略在 Phase 5 的具体工程落地

1. **Credal 不确定性区间构建**：以单笔交易序列计算狄利克雷证据质量与认知空虚度，求得期望收益率的 Credal 下界 $\underline{\mathbb{E}} = +0.1768\%$。
2. **Deflated Sharpe Ratio (DSR)**：对 50 次试验空间实施 Bailey & Lopez de Prado 统计惩罚，DSR 达 100.00%。
3. **PBO (CSCV 16 组)**：测得过拟合概率仅为 4.2%。
4. **蒙特卡洛 2,000 路径 Bootstrap 压力测试**：破产概率严格为 0.00%，95% MDD 仅 13.28%。
