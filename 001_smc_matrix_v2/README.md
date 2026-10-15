# SMC V2 策略组件与 15 分钟周期全量决策逻辑归因规范

本项目归档并重建了当前正在运行的 **NautilusTrader 4-Asset Trend Pullback & Evidential Volatility Filter (SMC V2)** 生产级事件驱动量化交易策略。

---

## 一、策略组件架构概览

策略部署于 `/opt/nautilus`，由以下核心组件共同协作构成：

1. **`smc_live_trader.py` (交易策略主程序)**
   - **标的池**：`BTC-USDT-SWAP`、`ETH-USDT-SWAP`、`SOL-USDT-SWAP`、`BNB-USDT-SWAP`（OKX 永续合约）。
   - **周期**：15 分钟 K 线（15-Minute Bars）。
   - **NautilusTrader 核心引擎**：基于 `TradingNode`、`OKXDataClient`、`OKXExecutionClient` 构建的事件驱动异步架构。
   - **特征提取与信号评分 (`TechnicalFeatures`)**：
     - EMA 20/50 趋势追踪体系；
     - 局部高低点与市场结构（SMC / Market Structure Break）；
     - RSI 超买超卖与均值回归；
     - 动量与趋势回调综合评分（满分 10.0，阈值 `>= 5.0`）。
   - **狄利克雷主观逻辑不确定性过滤器 (`DirichletFilter`)**：
     - 贝叶斯信度论网关：计算证据不确定度 $u$ 与置信度 $C$；
     - 过滤震荡锯齿行情（Chop Filter），仅在 $u \le 0.35$ 且 $C \ge 0.40$ 时放行信号。
   - **组合并发保证金协调器 (`PortfolioCoordinator`)**：
     - 全资产持仓上限限制（最大并发持仓数限制为 2）；
     - 多标的同根 Bar 同时触发信号时，按评分权重智能切分风险预算与可用保证金。
   - **生产级容错机制**：
     - 纯字母数字 Client Order ID 保证，杜绝 OKX 拒单；
     - GTC 挂单 3 根 Bar 超时自动撤单；
     - 连续 3 笔亏损熔断保护，进入 48 根 K 线（12小时）冷却机制；
     - 重启自动继承已存持仓（Hydration）与启动即刻补齐 60 根历史 K 线冷启动（Cold-start Warmup）。

2. **`smc_health.py` (系统健康巡检监控器)**
   - 监听 Docker 容器健康状况、OKX WebSocket 延迟、网络心跳与保证金率警报。

3. **`docker-compose.yml` (容器化编排环境)**
   - 管理 `nautilus-okx-demo` 交易容器与 `nautilus-redis` 缓存数据库。

4. **`DEMO_TRADING_SINCE_20261002_UTC0125.log.gz`**
   - 包含从 UTC 2026-10-02 01:25:00 至今的模拟盘全量原生运行与交易日志。

---

## 二、每 15 分钟 Bar 的决策逻辑与策略规则归因

在策略的 `on_bar(self, bar: Bar)` 回调中，每 15 分钟触发一次完整的决策流水线。每一根 K 线结束时，策略的行为**严格且确定性地遵循以下 8 大规则之一**：

```
[新 15m K线到达 on_bar]
         │
         ├──► [规则 1] 挂单超时判定 (Pending Order Timeout Check)
         │       └─ 条件: 存在在途未成交限价开仓单且挂单历时 >= 3 根 Bar
         │       └─ 动作: 撤销挂单 (主动撤单 TTL=3)，本周期不进行新开仓
         │
         ├──► [规则 2] 在途持仓管理 (In-Position Active Management)
         │       └─ 条件: 账户当前持有该标的多/空头头寸 (in_position == True)
         │       ├─ 子规则 2.1 止损平仓 (STOP_LOSS): 触及 entry ± 1.5 * ATR (或 0.5% 兜底)
         │       │    └─ 动作: 市价单平仓 (REDUCE_ONLY MARKET EXIT)
         │       ├─ 子规则 2.2 止盈平仓 (TAKE_PROFIT): 触及 entry ± 3.0 * ATR
         │       │    └─ 动作: 市价单平仓 (REDUCE_ONLY MARKET EXIT)
         │       └─ 子规则 2.3 继续持有 (HOLD): 价格在止损与止盈区间内震荡
         │            └─ 动作: 不操作，心跳汇报当前浮动盈亏
         │
         ├──► [规则 3] 连续亏损熔断冷却判定 (Loss Streak Breaker)
         │       └─ 条件: 最近连续平仓亏损达到 3 次 (consec_losses >= 3)
         │       ├─ 冷却中: breaker_bars < 48 根 K 线 (12小时)
         │       │    └─ 动作: 强制不操作，暂停新信号开仓
         │       └─ 冷却期满: breaker_bars >= 48 根 K 线
         │            └─ 动作: 重置熔断计数器，恢复正常监听
         │
         ├──► [规则 4] 组合全局并发风控判定 (Portfolio Coordinator Cap)
         │       └─ 条件: 当前标的池中已有 2 个或以上币种处于开仓状态
         │       └─ 动作: 触发风控拦截，不操作 (防止全市场 Beta 同步下挫)
         │
         ├──► [规则 5] 技术形态信号评分判定 (Technical Feature Score)
         │       └─ 条件: EMA/结构/RSI 综合评分计算
         │       ├─ score_long < 5.0 且 score_short < 5.0:
         │       │    └─ 动作: 不操作 (无有效方向性动能信号)
         │       └─ 评分最高方向 >= 5.0:
         │            └─ 动作: 生成候选信号 (DIRECTION = 1 多 / -1 空)，进入主观逻辑过滤网关
         │
         ├──► [规则 6] 狄利克雷主观逻辑不确定性网关 (Evidential Gate Filter)
         │       └─ 计算: 依据多空证据计算信度分布，导出不确定度 u 和冲突度 C
         │       ├─ u > 0.35 或 C >= 0.40:
         │       │    └─ 动作: 拦截信号，判定为高风险锯齿震荡区 (Chop Regime)，不操作
         │       └─ u <= 0.35 且 C < 0.40 (Gate Passed):
         │            └─ 动作: 网关放行，信号有效，提交至并发切分协调器
         │
         ├──► [规则 7] 并发保证金切分与执行 (Concurrent Batch Sizing & Execution)
         │       └─ 计算: 读取账户 USDT 实时权益，计算 1% 单笔风险预算；多标的同根 Bar 触发时按 score 分数加权分配
         │       └─ 动作: 提交开仓委托 (Market/Limit Entry Order)
         │
         └──► [规则 8] 撮合成交与状态机转换 (Fill Confirmation)
                 └─ 触发: 收到交易所 on_order_filled 事件
                 └─ 动作: 更新真实净持仓 (Real NetPos)，正式建立 in_position 状态，设立动态止损与止盈价位
```

---

## 三、交易日志与判定规则映射示例

| 时间 (UTC) | 标的 | 触发事件 / 日志关键字 | 命中规则归因 | 决策判定与操作结果 |
|---|---|---|---|---|
| `2026-10-13 11:30` | `ETH-USDT-SWAP` | `[HEARTBEAT] Px=2504.54 \| InPos=True` | **规则 2.1 (STOP_LOSS)** | 价格打到止损阈值，触发 `EXIT CONFIRMED` 市价减仓平仓 |
| `2026-10-13 11:34` | `BTC-USDT-SWAP` | `SIGNAL: LONG \| Score=7.2 \| Evidential u=0.180, C=0.210 \| Gate Passed: True` | **规则 5 + 规则 6 + 规则 7** | 评分 7.2 高于阈值，狄利克雷过滤器放行，按 1% 风险切分预算开多 193 张 |
| `2026-10-13 11:15` | `SOL-USDT-SWAP` | `Limit entry order unfilled after 3 bars (>= 3 bars limit). Cancelling...` | **规则 1 (Pending Timeout)** | 挂单超时 3 根 Bar 未成交，主动撤单，防止不利价格追单 |
| `2026-10-13 11:00` | `BNB-USDT-SWAP` | `[HEARTBEAT] InPos=False \| NetPos=0.0` (且无信号) | **规则 5 (Score < 5.0)** | 当前 K 线结构无明显单边趋势，评分不足，保持空仓待机 |
| `2026-10-12 16:00` | `BTC-USDT-SWAP` | `PortfolioCoordinator: Active positions >= 2, open rejected` | **规则 4 (Cross-Asset Cap)** | 已持有 ETH 和 SOL 仓位，触发组合并发拦截，本周期不操作 |
