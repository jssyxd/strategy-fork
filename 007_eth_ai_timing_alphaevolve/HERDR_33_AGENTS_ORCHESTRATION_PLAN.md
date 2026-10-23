# Herdr 多 Agent 编排流水线：33 个微粒度单点 Agent 拓扑规划蓝图

严格遵照 SPEC-008 规范，每个 Agent 仅执行单一窄边界任务，严防上下文膨胀与幻觉造假。每个 Worker Agent 交付物必须附带【数据来源声明】，经 Chief-Auditor 独立物理核实验收后，方准使用 `herd-dispatch stop --name ... --yes` 关闭并推进下一步。

---

## 阶段一：数据底座与不变性物理断言审计（6 个 Agent）
- **Agent 01: `data-inspector`** (模型: `pi`)
  - 任务: 穿透审查本地 `/home/da/桌面/database/` 下治理湖 Parquet 文件元数据、列定义、数据行数与文件哈希。
- **Agent 02: `ts-monotonic-guard`** (模型: `codex`)
  - 任务: 编写并执行时间戳单调递增性（断言 1）与零重复时间戳（断言 2）的物理校验代码。
- **Agent 03: `gap-continuity-guard`** (模型: `codex`)
  - 任务: 编写并执行无时间断流连续性检验（断言 3），定位所有 Gap > 15m 的异常。
- **Agent 04: `kline-geometry-guard`** (模型: `codex`)
  - 任务: 编写并执行 K 线高低倒挂（High < Low, Open/Close 溢出）几何包络自洽性（断言 4）。
- **Agent 05: `data-cleanliness-guard`** (模型: `pi`)
  - 任务: 编写并执行正定价、非负成交量（断言 5）与零 NaN 空值填充率（断言 6）物理断言。
- **Agent 06: `anti-lookahead-guard`** (模型: `claude`)
  - 任务: 验证事件闭合因果断言（断言 7），对齐 `ts_init` 与 `ts_event`，物理上杜绝使用当根收盘价即时成交的未来函数。

---

## 阶段二：微观特征工程与 Q-State 状态方程构建（5 个 Agent）
- **Agent 07: `feat-ret-momentum`** (模型: `codex`)
  - 任务: 纯数学实现无未来函数的对数收益动能 `RET = ln(C_t / C_{t-1})` 与滚动加速度。
- **Agent 08: `feat-body-imbalance`** (模型: `codex`)
  - 任务: 实现柱体与高低振幅失衡代理 `IMBALANCE = (C_t - O_t) / (H_t - L_t + eps)`。
- **Agent 09: `feat-extreme-breakout`** (模型: `codex`)
  - 任务: 实现 16 周期极值通道突破位置 `BREAKOUT` 分位特征。
- **Agent 10: `feat-ma-deviation`** (模型: `pi`)
  - 任务: 实现 20 周期均线标准化偏离度 `DEVIATION = (C_t - SMA20) / ATR14` 与真实波动幅度。
- **Agent 11: `q-state-recursive-engine`** (模型: `codex`)
  - 任务: 编写带折现因子的时序差分状态机核心 $S_t = \gamma S_{t-1} + (1-\gamma) R_t$ 递归函数。

---

## 阶段三：双轨执行机与风控边界实现（5 个 Agent）
- **Agent 12: `entry-router-50`** (模型: `codex`)
  - 任务: 实现 15m BarClose 确权入场逻辑，当 $S_t > \text{Th}_{50}$ 且持仓为空时，次根开盘以市价下单 50% 保证金首仓。
- **Agent 13: `entry-router-75`** (模型: `codex`)
  - 任务: 实现顺势加仓逻辑，当 $S_t > \text{Th}_{75}$ 且已持有一档仓位时，次根开盘以可用资金 75% 顺势加仓。
- **Agent 14: `exit-trail-stop`** (模型: `codex`)
  - 任务: 实现盘中微观动态移动追踪止盈 Trailing Stop 触发机制。
- **Agent 15: `exit-hard-stop`** (模型: `codex`)
  - 任务: 实现 $-2.50\%$ 物理硬止损截断机制，绝不死扛。
- **Agent 16: `exit-time-stop`** (模型: `pi`)
  - 任务: 实现持仓达到 202 根 15m Bar (50.5小时) 的时间止损机制，防范长久横盘磨损。

---

## 阶段四：真实 Kaggle 云端调度与状态轮询（4 个 Agent）
- **Agent 17: `kaggle-credential-validator`** (模型: `pi`)
  - 任务: 校验本地 `~/.kaggle/access_token` 有效性，执行 `kaggle quota` 检查 GPU/TPU 真实配额。
- **Agent 18: `kaggle-kernel-packager`** (模型: `codex`)
  - 任务: 将 AlphaEvolve 符号回归训练代码与数据切片配置规范封装为 Kaggle Kernel 目录与 metadata。
- **Agent 19: `kaggle-gpu-dispatcher`** (模型: `codex`)
  - 任务: 真实执行 `kaggle kernels push` 推送到 `opclown1/eth-ai-alphaevolve-gp-q-learning-trainer` 并轮询其状态。
- **Agent 20: `kaggle-output-harvester`** (模型: `pi`)
  - 任务: 监控云端直至 `COMPLETE`，执行 `kaggle kernels output` 真实拉取 Checkpoint 权重与真实运行日志。

---

## 阶段五：双引擎独立回测与交叉对账（5 个 Agent）
- **Agent 21: `vbt-standalone-engine`** (模型: `codex`)
  - 任务: 独立编写并运行 VectorBT PRO 向量化张量回测脚本，输出 `vbt_metrics.json`。
- **Agent 22: `nautilus-standalone-engine`** (模型: `cursor`)
  - 任务: 独立编写并运行 NautilusTrader 2.0.0rc6 事件驱动策略，输出 `nautilus_metrics.json`。
- **Agent 23: `dual-metrics-comparator`** (模型: `claude`)
  - 任务: 逐项对比双引擎的交易总笔数、累计收益率、最大回撤、胜率等核心指标。
- **Agent 24: `dual-attribution-analyzer`** (模型: `claude`)
  - 任务: 穿透分析撮合时钟边界与出场点差异，生成客观归因树。
- **Agent 25: `zero-fabrication-auditor`** (模型: `claude`)
  - 任务: 独立审查数字来源声明，严禁任何数据迎合与编造。

---

## 阶段六：红队白帽对抗断头台与黑天鹅压力测试（4 个 Agent）
- **Agent 26: `goodhart-trap-slayer`** (模型: `claude`)
  - 任务: 强制注入 3~6 bps 现实微观滑点，检验是否存在度量异化刷分漏洞。
- **Agent 27: `black-swan-guillotine-tester`** (模型: `codex`)
  - 任务: 强制在 2024-08-05 黑色星期一暴跌（单 Bar 跌 -17.69%）断头台区间运行，检验是否穿仓。
- **Agent 28: `deflated-sharpe-auditor`** (模型: `claude`)
  - 任务: 计算考虑多轮试错次数扣减后的 Deflated Sharpe Ratio (DSR) 真实统计显著性。
- **Agent 29: `square-root-impact-simulator`** (模型: `codex`)
  - 任务: 注入 Almgren-Chriss 平方根市场冲击模型与 100ms 网络延迟。

---

## 阶段七：生产交付物编译、审计与 CI/CD 部署（4 个 Agent）
- **Agent 30: `pine-script-v6-builder`** (模型: `codex`)
  - 任务: 将收敛后的确定性参数编译导出为 TradingView Pine Script v6 生产脚本。
- **Agent 31: `event-cicd-workflow-architect`** (模型: `codex`)
  - 任务: 编写基于 4 大事件源驱动的 GitHub Actions 自动化 CI/CD 流水线。
- **Agent 32: `chief-auditor-signer`** (模型: `claude`)
  - 任务: 全量审核所有前序 Agent 交付物，签署数字来源与物理真实性合格证书。
- **Agent 33: `production-git-deployer`** (模型: `pi`)
  - 任务: 规范化 Commit 并 Push 最终整套生产工程至目标 GitHub 仓库。
