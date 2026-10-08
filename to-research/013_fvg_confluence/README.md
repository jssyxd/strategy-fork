# 策略 013：公允价值缺口五层共振（`fvg_confluence`）

| 项 | 内容 |
| :--- | :--- |
| 策略编号 | **013** |
| 策略英文名 | `fvg_confluence` |
| 来源 | 由微信联系人提供的 TradingView Pine 脚本 `公允价值缺口.txt`（646 行，位于工作区根目录，**未纳入本仓库**） |
| 原始形态 | **指标，非策略**（`strategy()` 0 处、`alertcondition` 0 处、`//@version=` 缺失）→ 不可直接回测，需补写为可执行策略 |
| 回测引擎 | nautilus_trader **2.0.0rc6**（服务器 `/root/nautilus2-venv`，撮合为 Rust 实现） |
| 运行位置 | 服务器，全部经 systemd 瞬态 cgroup 限额（`MemoryMax` / `CPUQuota` / `Nice`） |
| 回测窗口 | 2024-10-01 → 2026-10-08（24.2 个月） |
| 当前状态 | **主判定不通过**（成本结构不成立）；验收项尚有 6 项未完成，详见第七节 |
| 规格书 | [BACKTEST_SPEC.md](./BACKTEST_SPEC.md)（v2.2 冻结）与 [SPEC_REVIEW.md](./SPEC_REVIEW.md)（对抗性评审 31 项） |

---

## 一、目标基准定义（预注册，研发成功的唯一判据）

本策略无外部公开业绩基准，目标基准为**回测前冻结的验收阈值**（规格书 5.4）。
**预注册的主判定配置：BTC-USDT-SWAP · 15m · A 口径（1× 名义）· TP1 减半仓 · √365**。
其余全部配置（ETH / SOL、1h / 4h / 1d、B 口径、√252）一律标 **exploratory：只报不判定**。

| 维度 | 指标 | 阈值 |
| :--- | :--- | :--- |
| 样本量 | `closed_trade_count` | ≥ 200（< 200 判「不充分」，不得写成「不通过」） |
| 主判据 | 每笔净期望 `avg_pnl` | > 0 且 t ≥ 2 |
| 样本外 | `total_return_pct` / `sharpe_ratio` / `max_drawdown_pct` | > 0 / ≥ 0.8（√365，√252 对应 ≥ 0.66）/ ≤ 25%（B 口径） |
| 相对基准 | `information_ratio`（A 口径 vs 买入持有） | ≥ 0 |
| 对照组 | 每笔期望差值（策略 − 随机入场） | 95% 置信区间不含 0 |
| 成本体检 | (`total_commission` + `total_funding`) ÷ `gross_pnl` | ≤ 40% |
| 稳健性 | WSR / 参数 ±20% / 蒙特卡洛 | 正收益窗口占比 ≥ 60%；参数扰动符号不变；MC 10000 次 5% 分位回撤 ≤ 40% |

---

## 二、策略文件是哪个（重要）

**策略本体由两个文件组成，缺一不可：**

| 文件 | 行数 | 职责 |
| :--- | ---: | :--- |
| **[src/fvg_rules.py](./src/fvg_rules.py)** | 257 | **规则层**：纯函数、全因果、零依赖。把 Pine 的指标（EMA 带、ATR、ADX、Squeeze 动量、量差、OBV、日锚 VWAP）、FVG 状态机（检测 / 失效 / 回踩扫描）与五层共振门控算成数组，产出每根 K 线的信号与入场位 |
| **[src/run_bt2.py](./src/run_bt2.py)** | 404 | **执行层**：其中的 `Runner(Strategy)` 即 nautilus 策略类——按信号下单、挂止损止盈条件单、逐根上移移动止损、反手先平后开、按 5% 风险反推仓位，并做**逐笔对账记账**；同时是命令行入口 |

### ⚠️ 废弃文件（勿用，仍在 `src/` 内）

| 文件 | 行数 | 为什么废弃 |
| :--- | ---: | :--- |
| `src/fvg_strategy.py` | 190 | 第一版**增量式指标**写法，已被纯函数规则层 `fvg_rules.py` 取代；两者逻辑重复，改动请只改后者 |
| `src/run_bt.py` | 400 | 第一版执行器，**含对账缺陷**：用 `equity_after − equity_before` 计算每笔盈亏，而成交回调触发时账户状态尚未计入该笔手续费，导致 1,186 笔累计少记约 4,000 USDT（详见 [reports/reconciliation_fix.md](./reports/reconciliation_fix.md)） |

> 结果文件的区分：`results/btc15m_A_half_v2.json` 是**修复后**的结果；
> `results/btc15m_A_half.json` 是旧账，**不要引用**。

### 探针脚本（冒烟测试记录，非策略代码）

`src/smoke_*.py` 共 11 个 + `src/diag_rules.py`：用于确认引擎语义（成交时点、同根止损/止盈顺序、资金费挂钩、BarType）与规则漏斗诊断。
结论见 [reports/smoke_report.md](./reports/smoke_report.md)，**不要把它们当成策略实现**。

---

## 三、目录结构

```
013_fvg_confluence/
├── README.md                       ← 本文件
├── SPEC_REVIEW.md                  ← 对抗性评审（31 项漏洞与处置）
├── src/
│   ├── fvg_rules.py                ★ 规则层（策略本体之一）
│   ├── run_bt2.py                  ★ 执行层（策略本体之二）+ CLI
│   ├── run_matrix.py               24 组批量驱动
│   ├── regen_report.py             从原始结果生成报告
│   ├── build_catalog.py            JSONL → ParquetDataCatalog
│   ├── pull_data.py                拉 OKX K 线与资金费
│   ├── fvg_strategy.py             ✗ 废弃（v1 增量式）
│   ├── run_bt.py                   ✗ 废弃（v1 含对账缺陷）
│   ├── diag_rules.py               规则漏斗诊断
│   └── smoke_*.py                  引擎语义探针（11 个）
├── reports/
│   ├── smoke_report.md             冒烟测试报告（四项结论）
│   └── reconciliation_fix.md       对账问题根因与修复
├── results/
│   ├── backtest_report.md          ★ 回测报告（24 组全表 + 成本分解）
│   ├── summary_fixed.json          24 组汇总（修正 gross/net 定义后）
│   ├── btc15m_A_half_v2.json       主判定组完整结果（1,186 笔明细）
│   └── btc15m_A_half.json          ✗ 旧账，勿引用
└── data/                           （在服务器 /root/bt013/data，未入仓）
```

---

## 四、策略规则摘要

完整规则（含 Pine 原文行号）见 [BACKTEST_SPEC.md 第一节](./BACKTEST_SPEC.md)。要点：

1. **FVG 检测**：三根 K 线结构，多头 `low > high[2]`；位移根实体 ≥ 14 根平均实体 × 1.15；缺口 ≥ 0.15 × ATR(10)；仅收盘确认（无重绘）。
2. **回踩入场**：未失效、缺口年龄 ≤ 120 根、与当前 K 线区间重叠、且收盘满足中场（CE）拒绝。
3. **五层共振**：EMA 带 / Squeeze 动量 / 量差+OBV / VWAP / ADX 方向，至少 3 层同意。
4. **门控**：交易时段 07:00–20:00（主口径按北京时间）、信号冷却 8 根、趋势对齐。
5. **出场**：SL = FVG 远边 − 1.2×ATR；TP1 = +1.8×ATR（减半仓）；TP2 = +3.5×ATR；移动止损 1.5×ATR 逐根上移。
6. **状态机**：单标的、单向、无加减仓，反向信号直接反手。

**参数全部为 Pine 脚本默认值，回测期间未做任何调参。**

---

## 五、执行口径与已批准偏离

| 项 | 规格书要求 | 引擎实际 | 处置（已批准） |
| :--- | :--- | :--- | :--- |
| 成交时点 | 信号根次根**开盘**成交 | 提交当根**收盘**成交 | 策略层延后一根提交 → 实际为「次根收盘」成交 |
| 同根止损/止盈 | **先止损**（悲观） | **先止盈**，两条都成交且无滑点 | 主表按引擎原生出；悲观版待后处理（未完成） |

其他口径：手续费 taker 0.05%（本账户实盘日志实测）；A 口径 = 每笔名义 = 权益 × 1；B 口径 = 单笔风险 = 权益 × 5%、名义上限 20×、初始权益 10,000 USDT；引擎原生 K 线撮合。

---

## 六、当前结果（2026-10-08）

**主判定组（BTC · 15m · A 口径 · 减半仓）：不通过。**

| 指标 | 值 | 判定 |
| :--- | ---: | :--- |
| 已完成交易数 | 1,186 | 样本充足 |
| 每笔净期望 | **-4.58 USDT** | 不通过 |
| t 统计量 | -3.59 | 不通过 |
| 总收益 / 最大回撤 | -54.26% / 55.23% | 不通过 |
| Sharpe（√365） | -2.49 | 不通过 |
| 成本 ÷ 毛边际 | **418%** | 触发「成本结构不成立」 |

**关键发现（成本结构）**：15 分钟周期上**毛边际为正**（BTC +1.44、ETH +2.88 USDT/笔），
但往返成本 6–7 USDT/笔，是边际的四倍以上。成本占比随周期单调下降：
15m 242–418% → 1h 61–63% → 4h 26% → 日线 4–19%。
但长周期交易数只有 23–97 笔，按规格书判**不充分**，不作为结论。
唯一「≥ 200 笔且净正」的是 SOL 1h（349 笔，A +20.71% / B +69.26%），
但回撤 34–38% 超阈值、Sharpe 一套过一套不过 → 按预注册规则只能标为**边缘**。

**对账**：24 组全部做到自建权益 = 引擎权益（最大差额为浮点误差级）。

---

## 七、未完成清单（验收前必须补齐）

1. **资金费后处理**（规格书 3.4）——引擎无原生支持，需 `SimulationModule` 或后处理扣减；
2. **同根止损/止盈悲观版**（规格书 3.6）——后处理改判并报受影响笔数占比；
3. **OOS 一次性验证**（2026-04-01 → 2026-10-08）；
4. **稳健性检验**：WSR / 参数 ±20% / 蒙特卡洛 10000 次 / 随机入场对照组 1000 次；
5. **TP1 不减仓对照**；
6. **组合回测**（三标的共享权益，规则见规格书 3.7）。

---

## 八、运行方式

```bash
# 1) 拉数据（服务器，约 7 分钟）
python pull_data.py

# 2) 建 catalog（服务器）
python build_catalog.py

# 3) 单组回测：<标的> <周期> <A|B> <half|full> <起> <止> [输出 json]
python run_bt2.py BTC-USDT-SWAP 15m A half 2024-10-01 2026-10-08 results/out.json

# 4) 24 组矩阵 + 报告
python run_matrix.py
python regen_report.py
```

服务器上跑长任务时统一用 cgroup 限额（保护实盘 `smc-trader`）：

```bash
systemd-run --unit=bt013-RUNID -p MemoryMax=500M -p CPUQuota=80% -p Nice=10 \
  -p WorkingDirectory=/root/bt013 /root/nautilus2-venv/bin/python run_bt2.py ...
```

---

## 九、数据

| 项 | 值 |
| :--- | :--- |
| 标的 × 周期 | BTC / ETH / SOL × 15m / 1h / 4h / 1d |
| K 线总数 | 293,588 根（parquet catalog 9.6MB） |
| 资金费 | 3 个标的各约 940 条结算记录（2024-09 起） |
| 合约规格快照 | `data/instruments_swap.json`（500 个 SWAP，含 tick / lot / ctVal / minSz） |
| 未收盘 K 线 | 每个文件各剔除 1 根 |

---

*本 README 记录截至 2026-10-08 的实际状态。所有数字来自原始结果 JSON，未手工修改。*
