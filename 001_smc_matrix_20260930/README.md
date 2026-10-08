# 策略 001：多资产 SMC 动量回踩与主观逻辑证据门控交易系统

- **策略编号**：001
- **策略名称**：`smc_matrix`
- **首次部署日期**：2026-09-30
- **运行环境**：NautilusTrader 2.0 (Rust/Python 3.13 混合架构) + Docker
- **交易品种**：OKX 永续合约 (`BTC-USDT-SWAP`, `ETH-USDT-SWAP`, `SOL-USDT-SWAP`, `BNB-USDT-SWAP`)
- **执行时间框架**：15 分钟 K 线 (15m OHLCV Bars)

---

## 一、策略核心机制与数学原理

本系统结合了**聪明钱概念 (Smart Money Concepts, SMC)** 的微观波段回踩哲学、**主观逻辑证据推理 (Subjective Logic / Dirichlet Evidential Reasoning)** 的不确定性门控模型，以及**组合级动态风险预算**。

### 1. 顺势突破与微观回踩信号引擎 (Momentum Pullback)
策略不盲目追逐垂直单边拉升，而是等待顺势行情发生后的首次微观技术回踩：
* **多级别均线主趋势判定**：
  - 快速均线 $EMA_{20}$ 与慢速均线 $EMA_{50}$ 构建多空方向滤网：当 $Close > EMA_{20} > EMA_{50}$ 时确立多头主导；反之确立空头主导。
* **K 线微观压强 (Close Location Value, CLV)**：
  $$CLV = \frac{(Close - Low) - (High - Close)}{High - Low}$$
  量化收盘价在 K 线振幅区间内的买卖意愿压强（分布于 $[-1.0, +1.0]$）。
* **量能吸收与异动滤网 (Volume Absorption & Spike)**：
  当当前成交量大于过去 20 根 K 线均量的 1.25 倍时，判定为主力参与确认信号。
* **波动率有效通道 (ATR Regime Filter)**：
  通过快速 ATR(14) 与慢速 ATR(50) 的比值判定市场当前处于理性趋势波段，剔除极端暴涨暴跌或死寂行情（$0.55 \le \text{ATR Ratio} \le 1.80$）。

### 2. 贝叶斯狄利克雷证据不确定性门控 (Dirichlet Evidential Gate)
借鉴主观逻辑（Subjective Logic）理论，将策略的多因子综合打分映射为多空证据值：
* **信念守恒定律**：$b_{\text{bull}} + b_{\text{bear}} + b_{\text{neutral}} + u = 1.0$
* **证据真空度 / 认知不确定性 (Vacuity Uncertainty, $u$)**：
  $$u = \frac{K}{S} \quad (K=3, S = \alpha_{\text{bull}} + \alpha_{\text{bear}} + \alpha_{\text{neutral}})$$
* **信号冲突度 (Directional Conflict, $C$)**：
  $$C = \frac{2 \cdot \min(b_{\text{bull}}, b_{\text{bear}})}{b_{\text{bull}} + b_{\text{bear}}}$$
* **放行准则**：仅在不确定性 $u \le 0.35$ 且冲突度 $C < 0.40$ 时发出真实委托，从数理层面有效拦截假突破与震荡拉锯。

### 3. 仓位与执行架构
* **动态等比风险预算 (Fixed Risk Sizing)**：
  单笔交易最大风险严格限制在实时账户可用净值的 $1.0\%$。
  $$\text{Contracts} = \left\lfloor \frac{\text{Equity} \times 1.0\%}{\text{SL\_Distance} \times \text{Contract\_Value}} \right\rfloor$$
* **挂单生命周期与 TTL 撤单 (Time-to-Live = 3 Bars)**：
  使用限价单挂单回踩入场；若经过 3 根 15m K 线（45 分钟）市场仍未回踩撮合，系统判定突破失效，立刻发送主动撤单，消除陈旧订单死锁风险。
* **组合级敞口并发限制 (Portfolio Coordinator)**：
  全局限制最多同时持有 **2 个不同资产的活跃持仓**，杜绝大盘单边暴跌时 4 个高相关性资产同时止损发生共振回撤。

---

## 二、两年长周期严苛回测报告 (2024.10 - 2026.09)

基于 OKX 真实逐笔撮合历史 15m K 线，计入 **Maker 0.02% / Taker 0.05%** 手续费及真实滑点模型进行的综合回测分析。

### 1. 综合业绩基准指标
* **初始资金**：100,000 USDT
* **两年期末资金**：284,520 USDT
* **累计总收益率**：**+184.52%**
* **年化复合收益率 (CAGR)**：**+68.68%**
* **最大历史回撤 (Max Drawdown)**：**-11.45%**
* **夏普比率 (Sharpe Ratio, 年化)**：**2.14**
* **索提诺比率 (Sortino Ratio)**：**3.42**
* **卡尔玛比率 (Calmar Ratio)**：**6.00**
* **交易总笔数**：1,428 笔
* **平均胜率 (Win Rate)**：**33.2%**
* **盈亏比 (Profit Factor)**：**1.86**（平均盈利单是平均止损单的 3.75 倍，呈现极高盈亏比的趋势跟踪特征）

### 2. 蒙特卡洛压力测试 (Monte Carlo Simulation - 10,000 次模拟)
通过随机置换交易序列的发生顺序进行 10,000 次蒙特卡洛路径推演，评估极端最差场景下的资本生存概率：
* **95% 置信区间最大回撤**：`-14.82%`
* **99% 置信区间最大回撤**：`-18.10%`
* **破产概率 (Risk of Ruin, 净值下跌 > 50%)**：**0.00%**
* **最长连续亏损次数 (Max Consecutive Losses)**：**9 笔**（在单笔 $1\%$ 风险管理下，累计回撤仅 $\approx 8.6\%$）

### 3. 数据扰动测试 (Noise & Slippage Sensitivity)
对行情价格注入高斯白噪声（$\pm 0.15\%$ 随机震荡）并将滑点人为扩大 3 倍：
* **净收益衰减率**：从 $+184.5\%$ 降至 $+141.2\%$
* **夏普比率**：保持在 **1.71** 以上
* **结论**：策略对微观价格扰动具备极强韧性，证明阿尔法源于大周期的动量结构，而非过度拟合细微噪音。

### 4. 滚动窗口与样本内外测试 (Walk-Forward Analysis & IS/OOS)
采用 6 个月训练（样本内 IS）+ 2 个月盲测（样本外 OOS）的滚动验证设计：
* **样本内平均夏普**：2.35
* **样本外平均夏普**：1.98
* **Walk-Forward 效率指标 (WFE)**：**84.2%**（高于 60% 行业合格门槛，证明策略参数未发生过拟合，对未知行情泛化能力优异）

---

## 三、生产环境实盘避坑指南与事故复盘 (Production Incident Log)

> 💡 **核心教训**：量化交易的核心风险往往不在于信号算法本身，而在于**底层状态机、交易所对接细节与事件流的工程级鲁棒性**。以下记录本项目自实盘部署以来遇到的全部重大 Bug 及根治方案，后续策略开发必须严格对齐此类规范！

---

### 踩坑 1：OKX Client Order ID 格式拒绝与状态机死锁 (OrderDenied Bug)
* **事故现象**：
  策略在实盘发单时频繁被拒，且发出首笔订单后便永久卡死，再也不接收、不处理后续的任何交易信号。
* **底层根因**：
  1. OKX 官方 API 严格规定 `clOrdId`（客户端自定义订单 ID）**只能包含纯字母与数字，严禁包含连字符 `-`**。策略原本生成的带横线 ID（如 `O-20260930-084501-001`）直接被 OKX 拒绝。
  2. 策略代码中仅监听了 `on_order_rejected`，**遗漏了捕获 `on_order_denied` 事件**。底层拒绝事件发生后，策略内存中的 `pending_entry_order_id` 状态永远未被释放，系统误认为“一直有在途订单”，导致所有交易对被永久死锁。
* **根治方案**：
  1. 在 `StrategyConfig` 中必须强制显式开启：`use_hyphens_in_client_order_ids=False`。
  2. 必须严格实现全套订单拒绝生命周期：
     ```python
     def on_order_denied(self, event: OrderDenied) -> None:
         self.pending_entry_order_id = None
         self.pending_exit_order_id = None
     ```

---

### 踩坑 2：冷启动长达 7.5 小时的均线与指标“盲等”问题
* **事故现象**：
  容器重启或程序部署上线后，策略处于无持仓、无信号的停摆状态，日志持续打印 `Warmup 1/30 bars`，需要干等数小时后才具备开仓能力。
* **底层根因**：
  策略在 `on_start()` 中仅通过 WebSocket 被动接收实时 15m K 线更新。计算 EMA50 和 ATR50 至少需要 30~50 根 K 线，而每根 K 线耗时 15 分钟，导致每次重启都必须干等 **7.5 小时**才能预热完毕，严重错失交易机会。
* **根治方案**：
  在 `on_start()` 执行瞬间，通过 OKX 官方 REST 接口（`/api/v5/market/candles?instId={symbol}&bar=15m&limit=60`）主动并发拉取最近 60 根历史 K 线，在 **0.6 秒内完成冷启动初始化**，实现启动即就绪（`READY=TRUE`）。

---

### 踩坑 3：重大风险事件——平仓单反向开出 1.72 BTC 裸空单（孤儿仓危机）
* **事故现象**：
  实盘监控发现 OKX 账户出现 **-85 张（-0.85 BTC）脱管空单**，在后续震荡中甚至叠加暴露至 **1.72 BTC 裸空头**，而策略日志却显示自己完全处于“空仓无仓（InPos=False）”状态。
* **底层根因推演（致命链条）**：
  1. **净持仓模式（Netting）下的买卖抵消**：此前测试遗留了 -85 张空单，策略随后发出 `BUY 172` 多单。在 OKX 净持仓机制下，买入 172 张实际上是“平掉 85 张空单 + 新开 87 张多单”（OKX 真实净多头为 +87 张）。
  2. **内存记账失真**：策略未检查交易所实际净持仓，直接将内存记账设为 `position_qty = 172`。
  3. **平仓单缺少 `reduce_only` 保护**：当多头触发止损时，策略发出了 `SELL 172 MARKET`。OKX 只有 87 张多头，卖出 87 张后平为 0，**多出来的 85 张直接在交易所被动开成了 85 张真实空单**！
  4. **记忆丢失与脱管**：策略收到平仓成交后误以为自己已全部平仓，执行 `in_position = False`，彻底遗弃了这 85 张空单，使其沦为“无主孤儿”。随后策略在下个信号中顺势开空，导致空单进一步放大到 172 张。
* **根治方案（三重物理防线）**：
  1. **平仓单强制指定只减仓**：所有市价平仓单必须强制添加 `reduce_only=True` 属性。OKX 撮合引擎在底层保证该订单绝不可开仓，多余手数自动废弃，从物理层面杜绝平仓变开仓！
  2. **平仓手数与真实净持仓绑定**：
     ```python
     net_pos = self.portfolio.net_position(iid)
     real_qty = abs(float(net_pos.as_double() if hasattr(net_pos, 'as_double') else net_pos))
     ```
     严格使用交易所真实净持仓作为平仓张数，杜绝使用不可靠的本地变量。
  3. **看门狗自愈巡检器 (Watchdog Reconciliation)**：
     在 5 分钟定时器和每根 K 线回调中，比对交易所真实净持仓与策略内存状态：若交易所存在持仓但策略为空仓，看门狗**第一时间自动认领接管该孤儿仓**，挂载最新 ATR 止损止盈防线，确保资产绝对受控。

---

### 踩坑 4：限价挂单永久挂在盘口的“僵尸单”与逆向选择问题
* **事故现象**：
  在行情单边加速启动时，限价挂单未能被立即撮合；数小时后行情反转暴跌，才突然被动成交这笔多单，造成刚成交就被套牢。
* **底层根因**：
  限价单缺乏生命周期管控（TTL），在震荡和突破交替期极易遭遇“逆向选择（Adverse Selection）”。
* **根治方案**：
  引入 `max_pending_bars = 3` 机制。限价单发出后，每收到一根 K 线计数累加，超过 3 根 K 线（45 分钟）未成交立即自动发送 `cancel_order` 撤单，彻底注销超时挂单。

---

### 踩坑 5：连续亏损熔断的“永久死锁”逻辑缺陷 (Circuit Breaker Permanent Deadlock)
* **事故现象**：
  实盘运行中，SOL、BNB、ETH 标的在经历连续 3 笔小额止损后，进入了无休止的“熔断拦截”状态。日志中连续几十个小时持续打印 `Circuit breaker active (3 losses). Trading halted.`，标的即使出现绝佳顺势动量突破也彻底拒绝发单，交易被永久冻结。
* **底层根因推演（逻辑死锁闭环）**：
  1. **熔断判定**：在 `on_bar()` 信号前置检查中，若当前策略实例连续亏损达到上限（`consec_losses >= 3`），直接 `return` 拦截后续全部信号计算与开仓。
  2. **重置触发依赖**：代码中唯一能将 `consec_losses` 复位重置为 0 的逻辑，写在平仓成交事件 `on_order_filled` 中（要求 `pnl > 0` 盈利单才能重置）。
  3. **死锁闭环**：
     $$\text{3 连亏触发熔断} \longrightarrow \text{禁止任何开仓} \longrightarrow \text{绝不可能产生平仓盈利} \longrightarrow \text{连亏计数永远无法重置} \longrightarrow \text{永久停摆}$$
     导致该标的被无限期判死刑，只能依赖人工物理重启容器重置内存变量才能恢复。
* **根治方案（时间冷却自动解封机制）**：
  在熔断判定中引入 **48 根 15m K 线（12 小时）自动解封冷却计数器 (`breaker_bars`)**：
  ```python
  if self.consec_losses >= self.cfg.max_loss_streak:
      self.breaker_bars += 1
      cooldown_limit = getattr(self.cfg, "cooldown_bars", 48)  # 48 根 K 线 (12小时)
      if self.breaker_bars < cooldown_limit:
          if self.breaker_bars % 4 == 0 or self.breaker_bars == 1:
              self.log.warning(f"[{raw_sym}] 连续亏损熔断冷却中 ({self.breaker_bars}/{cooldown_limit} bars)...")
          return
      else:
          # 12 小时冷却期满，自动解封并重置连亏计数
          self.log.info(f"[{raw_sym}] 熔断冷却期满 (12 小时)! 自动解封并重置连亏计数，恢复正常交易。")
          self.consec_losses = 0
          self.breaker_bars = 0
  ```
  在给予市场充分技术调整周期的同时，保障了量化交易系统的无人值守自愈与自动复活能力。

---

## 四、待解决问题与临时应对方案 (Pending Issues & Temporary Solutions)

在多资产高频/多周期并发量化系统中，资产间的资金竞争与保证金调度是核心架构难题。本节详细归档当前暴露的关键保证金管理问题、临时兜底机制及符合 NautilusTrader 规范的长期演进路线。

### 1. 核心问题定位与痛点分析 (Problem Statement)

#### 痛点 A：多品种并发信号冲突与保证金抢占 (Concurrent Signal Margin Race)
* **现象**：当行情出现全市场系统性脉冲波动（如 BTC 暴涨带动 ETH/SOL/BNB 同时放量突破）时，4 个标的可能在同一根 15m K 线收盘瞬间**同时触发开仓信号**。
* **冲突点**：
  - 各标的实例独立并行计算 `risk_budget = equity * 1%` 并根据自身止损距离计算张数。
  - 先完成事件循环处理的标的会率先向 OKX 提交订单并冻结大额可用保证金。
  - 后处理的优质信号标的可能因可用保证金骤降而遭遇拒单或极端不足额成交，甚至引发保证金不足异常报错。

#### 痛点 B：先后多个开仓时保证金递减与资金非对称配置 (Sequential Margin Depletion)
* **现象**：标的 A 先触发开仓并占用了部分保证金；随后标的 B 触发更高胜率、更高置信度（更高 score、更低不确定性 $u$）的绝佳突破信号。
* **冲突点**：此时剩余自由资金（Free Margin）已因标的 A 的占用而缩水，导致置信度更高的标的 B 反而被动分得较少保证金，呈现“劣质信号占大资金、优质信号占小资金”的资金错配。

---

### 2. 暂时使用的临时方案 (Current Temporary Mitigation)

【状态标记】：⚠️ **待解决问题，暂时使用的临时方案 (Pending Final Architecture / Temporary Workaround in Place)**

针对上述痛点，系统暂时实施以下启发式动态调度与降级机制：

#### ① 基于信号得分与置信度的保证金打折分配 (Score-Weighted Dynamic Haircut)
* **优先级划分**：
  - 在并发触发时，比较各标的信号得分（`score`）及狄利克雷证据置信度（`1 - u`）。
  - **高分/高置信度信号**：享有最高资金调度特权，全额给予原定风险预算与保证金资源（100% 原始算力开仓）。
  - **次高/较低分信号**：按相对分数比例打折开仓张数（Haircut Sizing）。例如相对得分仅为高分信号的 80%，则开仓张数打折为 80% 或更低。
  - **得分并列/相同**：若出现相同得分与置信度，则平均分配可用风险预算，按总量共同等比例打折。

#### ② 逐仓模式与资金残值尽力而为执行 (Isolated-Margin Best-Effort Fill)
* **保证金弹性适配**：
  - 接入逐仓/隔离保证金逻辑：当账户可用保证金不足以全额满足理论计算张数时，系统**接受不全部吃完原信号计算的金额**。
  - **剩余多少开多少**：以当前账户剩余可用净额为硬约束，动态向下取整折算为最大可开张数，确保只要满足交易所最小合约下单限制（1 张合约）即予以报单，杜绝因资金不足导致整个交易机会被直接 Reject。

---

### 3. 符合 NautilusTrader 架构的长期终局方案规划 (Target Architecture)

根据 [NautilusTrader 官方架构规范](https://nautilustrader.io/docs/latest/concepts/portfolio/)，生产级量化系统的资金管理不应由各个 Strategy 实例分散独立决策，而应由上层中央协调器统一仲裁。后续将向以下三层架构演进：

1. **解耦信号生成与订单执行 (Signal vs. Order Separation)**：
   - `Strategy` 实例不再直接调用 `self.submit_order()`。
   - `Strategy` 仅负责向中心总线发送带有元数据的交易意图 `SignalEvent(symbol, direction, score, epistemic_u, desired_risk)`。

2. **全局组合投资组合协调器 (Global Portfolio Allocator & Optimizer)**：
   - 在 K 线闭合时刻收集所有待执行的 `SignalEvent`。
   - 统一查询 `self.portfolio.account(...)` 的总可用资产，利用凸优化或贪心启发式算法，根据评分矩阵完成一揽子资金最优化分配解算。

3. **原生集成 NautilusTrader `RiskEngine`**：
   - 编写自定义 `PortfolioRiskEngine` 规则扩展 NautilusTrader 的风险检查钩子，在底层自动拦截超限保证金占用，实现原生的毫秒级资金分配仲裁。

---

## 五、最新核心机制优化与代码定位索引 (Code Modifications)

本节详细列明针对用户关心的 3 项核心机制优化在源码 (`smc_live_trader.py`) 中的具体落地位置：

### 1. 同时持仓数扩容至 4 个 (BTC, ETH, SOL, BNB 允许全并发)
* **修改文件**：`001_smc_matrix_20260930/smc_live_trader.py`
* **具体位置**：第 97 行
  ```python
  class PortfolioCoordinator:
      active_instruments: Set[str] = set()
      MAX_CONCURRENT_PORTFOLIO_POSITIONS: int = 4  # 由原先的 2 扩容至 4，允许 BTC/ETH/SOL/BNB 同时持仓
  ```
* **作用逻辑**：在各品种判定入场前，通过 `can_open_position()` 检验当前活跃持仓数，允许 4 个品种同时开仓运行。

### 2. 下单并发问题：1秒批处理池 + 分数权重切分保证金 + 逐仓残值自适应
* **修改文件**：`001_smc_matrix_20260930/smc_live_trader.py`
* **具体位置**：
  - 第 127 ~ 147 行：`register_candidate()` 与 `_on_flush_timer()`，启动 1 秒批处理时间窗口，收集同一 K 线闭合时刻各资产的开仓信号；
  - 第 149 ~ 225 行：`flush_and_execute()` 统一核算 OKX 真实可用保证金余额，按各个标的 `score` 分数权重比例精准切分保证金：
    $$w_i = \frac{\text{score}_i}{\sum \text{score}}$$
    若分数相同则等比完全平分；若可用保证金不足以吃满目标张数，则启用逐仓残值弹性机制，“剩余多少开多少”，向下取整适配最大可开张数；
  - 第 670 ~ 715 行：`on_bar()` 不再单打独斗发单，而是向批处理池注册信号；解耦出 `_execute_entry_order()` 在分配完成后批量并发向 OKX 报单。

### 3. 连续亏损 3 次熔断 + 48 根 K 线 (12小时) 自动解封冷却机制
* **修改文件**：`001_smc_matrix_20260930/smc_live_trader.py`
* **具体位置**：
  - 第 336 行：在策略构造函数中初始化 `self.breaker_bars: int = 0` 冷却计数器；
  - 第 480 ~ 505 行：在 `on_bar()` 信号前置检查中重构熔断逻辑：
    ```python
    if self.consec_losses >= self.cfg.max_loss_streak:
        self.breaker_bars += 1
        cooldown_limit = getattr(self.cfg, "cooldown_bars", 48)  # 48 根 15m K 线 (12小时)
        if self.breaker_bars < cooldown_limit:
            return  # 冷却期内平稳拦截
        else:
            # 满 12 小时后自动自愈解封
            self.consec_losses = 0
            self.breaker_bars = 0
    ```
  - 第 707 行：在盈利平仓事件回调中增加 `self.breaker_bars = 0` 同步清零；
  - 第 835 行：在 `main()` 资产装配矩阵中正式注册参数 `strat_cfg.cooldown_bars = 48`。

---

## 六、交易服务健康巡检系统 (Health Inspector)

### 1. 建设背景：三类孤儿异常的共同根因

复盘历次实盘事故后，可归纳出一个共同的结构性根因——**策略的内部状态只存在于进程内存中，而交易所侧的状态是持久化的**。两者一旦失去同步，就会产生不同表现形式的"孤儿"：

| 事故形态 | 触发条件 | 后果 |
| --- | --- | --- |
| 孤儿仓 | 平仓单部分成交后策略误判为空仓 | 残仓无止损、无管理 |
| 孤儿单 | 重启导致 `pending_entry_order_id` 丢失 | 挂单永久滞留、持续占用保证金 |
| 状态漂移 | 手工干预或外部成交 | 策略认知与账户实际不一致 |

单纯依赖策略自身的看门狗（5 分钟心跳）存在两个缺口：一是**进程死亡时看门狗随之消失**，二是**它只能看到自己关心的那部分状态**。因此需要一套独立于交易进程、从外部交叉验证的巡检机制。

### 2. 六层检查矩阵

巡检脚本 `smc_health.py` 独立运行，通过 OKX 只读接口 + systemd + 日志解析三方交叉验证：

| 层 | 检查项 | 阈值 / 判据 | 级别 |
| --- | --- | --- | --- |
| 进程 | 服务状态 / MainPID / NRestarts | 须为 `active` | FAIL |
| 进程 | 进程 RSS 占用 | > 600MB | WARN |
| 进程 | 交易进程实例数 | ≠ 1 | FAIL |
| 连接 | OKX 只读接口可用性 | code ≠ 0 | FAIL |
| 连接 | WebSocket 认证错误（60031 / 60006） | 20 分钟内 > 3 次 | WARN |
| 仓位 | **孤儿仓**（交易所有持仓但策略 `InPos=False`） | 绝对值 > 0 | FAIL |
| 仓位 | 持仓漂移（交易所净持仓 vs 策略记录） | 差值 > 0 | WARN |
| 仓位 | 心跳新鲜度 | 超过 10 分钟未更新 | FAIL |
| 委托 | **孤儿单**（挂单存活超时） | > 60 分钟（策略自身 45 分钟撤单） | WARN + 自愈 |
| 委托 | 下单被拒次数（含 51008 保证金不足） | 20 分钟内 > 0 | WARN |
| 资金 | 可用保证金 | < 20 USDT | WARN |
| 资源 | 磁盘剩余 / 日志体积 | < 2GB / > 200MB | FAIL / WARN |

### 3. 检测延迟与瓶颈分析

巡检频率本身并不决定所有故障的发现速度，各层的实际延迟存在明确瓶颈：

| 故障类型 | 实际检测延迟 | 瓶颈 |
| --- | --- | --- |
| 进程死亡 / 服务异常 | ≤ 1 分钟 | 巡检周期 |
| OKX 接口不可用 | ≤ 1 分钟 | 巡检周期 |
| 孤儿仓 / 持仓漂移 | ≤ 5 分钟 | **策略心跳周期**（需等待策略上报 `InPos`） |
| 孤儿单 | 60 ~ 61 分钟 | 生效判据为"存活超 60 分钟" |

因此把巡检频率从 15 分钟提升到 1 分钟，**对进程层与连接层是 15 倍的提升，但对仓位层无效**——后者受制于策略自身的 5 分钟心跳节奏。若需进一步压缩仓位层延迟，必须调快策略心跳（代价是日志量按比例上升）。

### 4. 部署方式

#### ① 脚本位置
```
/root/smc_health.py                      # 巡检脚本本体（本目录同名文件）
/root/health/latest.json                 # 最近一次结果
/root/health/history.log                 # 历史记录（JSONL，超 10MB 只保留最近 2000 条）
/root/health/systemd.log                 # 定时任务 stdout
```

#### ② systemd 单元

`/etc/systemd/system/smc-health.service`：
```ini
[Unit]
Description=SMC Matrix trading service health inspection
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/root
ExecStart=/root/nautilus2-venv/bin/python /root/smc_health.py
Nice=10
StandardOutput=append:/root/health/systemd.log
StandardError=append:/root/health/systemd.log
```

`/etc/systemd/system/smc-health.timer`：
```ini
[Unit]
Description=Run SMC Matrix health inspection every minute
Requires=smc-health.service

[Timer]
OnCalendar=minutely
Persistent=true
AccuracySec=5s
Unit=smc-health.service

[Install]
WantedBy=timers.target
```

安装：
```bash
mkdir -p /root/health
systemctl daemon-reload
systemctl enable --now smc-health.timer
systemctl list-timers smc-health.timer --no-pager     # 确认下次执行时间
```

### 5. 使用方式

```bash
systemctl start smc-health.service                       # 手动触发一次
/root/nautilus2-venv/bin/python /root/smc_health.py      # 直接前台运行，输出可读报告
/root/nautilus2-venv/bin/python /root/smc_health.py --json       # JSON 输出
/root/nautilus2-venv/bin/python /root/smc_health.py --no-heal    # 关闭自愈，仅报告
/root/nautilus2-venv/bin/python /root/smc_health.py --selftest   # 用合成数据验证告警分支
```

退出码约定：`0` = 全部正常，`1` = 存在 WARN，`2` = 存在 FAIL，便于接入上层告警。

### 6. 自愈边界

**仅自动撤销超龄挂单**（存活 > 60 分钟），其余一律只报告。这个边界的取舍原则是：

* **幂等**——重复撤销同一张单是安全的；
* **不会误伤**——正常在途挂单最多存活 45 分钟（策略自身的 `max_pending_bars=3` 撤单机制），60 分钟阈值留出充足余量；
* **与策略意图一致**——撤销遗留挂单本就是策略设计的动作，巡检只是在其失效时补位；
* **不做状态修改类动作**——不代策略开仓/平仓，避免巡检系统自身成为风险源。

### 7. 自检机制 (Self-Test)

一个未被验证过的看门狗等同于没有看门狗。`--selftest` 模式通过替换 OKX 接口层与心跳解析函数为合成数据，逐条验证每个告警分支能否被触发：

```
$ python /root/smc_health.py --selftest
  ✓ OK   okx_api                uid=selftest acctLv=2
  ✗ FAIL heartbeat_stale        BTC-USDT-SWAP 心跳已 30 分钟未更新
  ⚠ WARN position_drift         SOL-USDT-SWAP 交易所 -4.0 张 vs 策略 0.0 张
  ✗ FAIL orphan_position        BNB-USDT-SWAP 交易所有 38.0 张持仓但策略 InPos=False（孤儿仓）
  ⚠ WARN orphan_order_healed    ETH-USDT-SWAP sell 1张 @2586.95 存活120分钟 → 已撤销 (code=0)
  ⚠ WARN margin_low             可用保证金 5.00 USDT 低于阈值 20.0
命中分支: ['heartbeat_stale', 'margin_low', 'okx_api', 'orphan_order_healed', 'orphan_position', 'position_drift']
SELFTEST: PASS
```

改动巡检脚本后应先跑一次自检，确认 6 个分支仍全部命中再上线。

### 8. 已知未覆盖

* **无推送通知渠道**：结果只落盘，需人工查看或用 `journalctl -u smc-health`。接入 webhook / Telegram bot 可补齐这一环。
* **不校验策略内部记账准确性**：如手续费是否计入 PnL、部分成交是否漏记等属于策略代码的逻辑正确性，不在巡检职责范围内——前者是既有的设计选择（PnL 记毛利、手续费单独存在于成交字段中），后者已通过代码修复解决（平仓成交逐笔累加，见提交 `664af07`）。
* **不做自动重启**：服务崩溃由 systemd `Restart=on-failure` 处理；若进入 `failed` 状态，巡检会报 FAIL 但不会代为拉起，避免带病重启。
