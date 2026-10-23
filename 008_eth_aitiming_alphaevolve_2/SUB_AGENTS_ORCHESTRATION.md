# 007 ETH AI 择时策略 (PROJECT-AE007-ADAPTIVE-SENTINEL)
## 36+ 子 Agent 协同研发、滚动训练与双引擎审计体系

本项目依据 SPEC+PRD 标准工业规范拆分为 **6 大专业集群、共计 36 个原子化子任务单元 (Atomic Sub-Agent Units)**，实现确定性管道驱动、零幻觉质检与责任闭环：

---

### 集群一：数据湖治理与时序不变性集群 (Data Governance & Invariance)
- **AG-01 (Lake Locator Agent)**: 定位并挂载本地治理湖与历史归档 Parquet，排查断流。
- **AG-02 (Timestamp Monotonicity Agent)**: 断言 `datetime` 严格单调递增，剔除重复纳秒戳。
- **AG-03 (Price Invariance Agent)**: 审查几何倒挂 ($High \ge Open, Close, Low$ 且 $Low \le Open, Close, High$)。
- **AG-04 (Volume & Price Positivity Agent)**: 审查价格正定性及成交量非负性。
- **AG-05 (Purge Buffer Auditor)**: 计算时序样本隔离区 (Purge $N=20$)，阻断跨窗口标签泄漏。
- **AG-06 (Embargo Boundary Agent)**: 计算样本外禁运区 (Embargo $N=10$)，彻底隔离自相关后向渗透。

---

### 集群二：特征工程与微观订单流集群 (Micro-Feature Engineering)
- **AG-07 (Log Return Agent)**: 计算无前瞻平稳对数收益率 ($RET_t = \ln(C_t / C_{t-1})$)。
- **AG-08 (Volume Acceleration Agent)**: 提取成交量 5 周期加速度 ($VOL\_ACCEL$)。
- **AG-09 (High-Low Spread Agent)**: 提取高低振幅相对波动率代理 ($HL\_SPREAD$)。
- **AG-10 (Bar Pressure Agent)**: 提取收盘位置压力比 ($K\_POS$)。
- **AG-11 (Candle Imbalance Agent)**: 提取实体力量失衡比 ($f_{imbalance}$)。
- **AG-12 (Donchian Breakout Agent)**: 提取 16 周期极值通道突破位置 ($f_{breakout}$)。

---

### 集群三：多岛屿自适应遗传演化集群 (Multi-Island GA & Evolution)
- **AG-13 (Island Topology Agent)**: 拓扑构建 5 个相互物理隔离的子种群岛屿。
- **AG-14 (Ring Migration Agent)**: 编排每 30 世代的环形优势基因迁移。
- **AG-15 (Cauchy Mutation Agent)**: 引入柯西重尾大步长随机突变，破坏局部极值收敛。
- **AG-16 (Cataclysmic Reset Agent)**: 监控连续停滞，触发全局灾变重启。
- **AG-17 (Fitness Objective Agent)**: 计算多目标适应度函数 (Calmar $\times$ 1.5 + Win $\times$ 10 - 15 $\times MDD^2$)。
- **AG-18 (Early Stopping Sentinel)**: 动态监控进化收敛斜率，触发早停节约无效算力。

---

### 集群四：悲观高保真撮合与双引擎对齐集群 (Pessimistic Execution & Dual-Engine)
- **AG-19 (Anti-Lookahead Open Agent)**: 强制当前 BarClose 信号在下一根 Bar Open 执行撮合。
- **AG-20 (Intra-Bar Ambiguity Agent)**: 柱内高低悲观仲裁（同根柱子触碰止损止盈时强制判定止损优先）。
- **AG-21 (Dynamic Slippage Agent)**: 注入波动率放大滑点模型 ($\text{Slip} = 1.5\text{bps} \times (1 + \text{ATR}/\mu_{\text{ATR}})$)。
- **AG-22 (Margin & Fee Auditor)**: 严格按 3.0x 名义价值 (Notional) 扣除 Maker 0.02% / Taker 0.05% 摩擦。
- **AG-23 (VectorBT Pro Alignment Agent)**: 执行向量化矩阵并行理论边界回测。
- **AG-24 (NautilusTrader Alignment Agent)**: 执行事件驱动纳秒级订单生命周期回测。

---

### 集群五：法医级全景消融实验集群 (Systematic Ablation Study)
- **AG-25 (Baseline Protocol Agent)**: 锁定全要素基准基线 (Baseline: Q-State + 75% 加仓 + 动态止盈 + 硬止损)。
- **AG-26 (Ablation-A Agent)**: 剥离 Q-State 时间差分算子，验证状态低通滤波真伪。
- **AG-27 (Ablation-B Agent)**: 禁用 75% 二次加仓，验证固定 50% 单笔持仓均价自愈效应。
- **AG-28 (Ablation-C Agent)**: 禁用盘中动态追踪止盈，验证 15m 级别的插针利润锁定价值。
- **AG-29 (Ablation-D Agent)**: 禁用 -2.5% 硬止损，检验极端单边流动性踩踏下的破产风险。
- **AG-30 (Ablation-E Agent)**: 杠杆 1.0x 现货等效归一化，证明内生 Alpha 与杠杆无关。
- **AG-31 (Wilcoxon Significance Agent)**: 双尾非参数 Wilcoxon 符号秩检验，输出各模块 p-value。

---

### 集群六：出厂准入门禁与三层 AI 哨兵集群 (Gatekeepers & Surveillance)
- **AG-32 (Gatekeeper-1 WinRate Agent)**: OOS 样本外胜率 $\ge 65.0\%$ 且平仓笔数 $\ge 10$ 笔质检。
- **AG-33 (Gatekeeper-2 Calmar Agent)**: OOS 样本外 Calmar 比率 $\ge 1.50$ 质检。
- **AG-34 (Deflated Sharpe Ratio Agent)**: 计算 DSR $\ge 0.80$ 检验多重测试选择偏差。
- **AG-35 (L1 Micro-Latency Sentinel)**: 监控毫秒级滑点 $> 5.0\text{ bps}$ 预警与开仓降级。
- **AG-36 (L2 Concept Drift Sentinel)**: 监控滚动 20 笔胜率 $< 65\%$ 与年化波动率暴涨 2.5 倍重训。
- **AG-37 (L3 Circuit Breaker Sentinel)**: 连续 3 笔硬止损封锁网关 48 小时；动态回撤 12% 强制清仓。
