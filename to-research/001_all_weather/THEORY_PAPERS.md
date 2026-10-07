# 理论论文与参考 (Theory Papers) — 策略 001 全天候 (All-Weather)

> 本目录 `papers/` 收录与该子项目直接相关的公开论文全文（arXiv 开放获取 PDF），并附 SSRN / DOI 链接。每篇论文均给出「为什么相关」的说明。

---

## 一、总体说明

本策略由三块理论拼成：①宏观周期判定与风险预算 → 组合优化 / 风险平价理论；②等风险贡献 (ERC) 权重求解 → 风险预算与协方差收缩；③深度虚值 (DOTM) 期权尾部对冲 → 期权定价与对冲。以下论文分别覆盖这三块。

---

## 二、arXiv 论文（全文 PDF 已随目录提供）

| # | 论文 | arXiv | 本地文件 | 为什么相关 |
| :--: | :--- | :--- | :--- | :--- |
| 1 | **Deep Learning for Portfolio Optimization** | [2005.13665](https://arxiv.org/abs/2005.13665) | [`2005.13665.pdf`](./papers/2005.13665.pdf) | 端到端深度学习直接输出组合权重，是「神经网络判定 + 组合分配」范式的规范性参考，对应本策略用网络做周期判定、再交由优化器分配仓位的两段式结构。 |
| 2 | **A Comparative Study of Hierarchical Risk Parity and Eigen Portfolios** | [2210.00984](https://arxiv.org/abs/2210.00984) | [`2210.00984.pdf`](./papers/2210.00984.pdf) | 系统比较 HRP 与特征组合（Eigen Portfolio）在样本外的表现，直接支撑本策略「等风险贡献 + 协方差收缩」的核心配置逻辑与其稳健性论证。 |
| 3 | **On Unified Adaptive Black-Litterman Mean-Variance Portfolio Management** | [2307.03391](https://arxiv.org/abs/2307.03391) | [`2307.03391.pdf`](./papers/2307.03391.pdf) | 自适应 Black-Litterman 的均值-方差统一框架，对应本策略把宏观观点（周期打分）注入基础权重并做动态倾斜的做法。 |
| 4 | **Physics-Informed Neural Network for Option Pricing** | [2312.06711](https://arxiv.org/abs/2312.06711) | [`2312.06711.pdf`](./papers/2312.06711.pdf) | 用物理信息神经网络求解期权定价 PDE，是本策略 DOTM 尾部对冲所需定价/希腊字母的计算基础。 |

---

## 三、SSRN / DOI 论文（链接）

> 说明：SSRN 对自动化访问启用了 Cloudflare 校验，本环境**无法抓取其正文 PDF**，故此处提供**官方链接 + 相关性说明**。链接与编号已通过 Crossref（DOI `10.2139/ssrn.*`）核对。

| # | 论文 | 链接 | 为什么相关 |
| :--: | :--- | :--- | :--- |
| 1 | **Building Diversified Portfolios that Outperform Out-of-Sample (López de Prado)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678> | 分层风险平价 (HRP) 的原始论文，风险预算类配置的对照基准。 |
| 2 | **Leverage Aversion and Risk Parity (Asness, Frazzini, Pedersen)** | <https://doi.org/10.2469/faj.v68.n1.1> | 风险平价的杠杆与风险偏好理论讨论，用于校准 ERC 权重与杠杆约束。 |
| 3 | **The Deflated Sharpe Ratio (Bailey, López de Prado)** | <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551> | 多重检验下的夏普比率收缩，用于防止本策略回测指标被过度乐观估计。 |

---

## 四、获取与引用约定

- arXiv 论文为开放获取，`papers/*.pdf` 为对应 arXiv 版本的全文副本；引用请以 arXiv 编号为准。
- SSRN 论文正文受站点防护限制未能随目录提供，请通过上表链接访问。
- 本目录仅用于技术研究与复现参考，版权归原作者所有。
