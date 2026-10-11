# 策略 010：BTC 15m 高频波段与资金流追踪 —— 生产级真实回测与审计报告

- **策略编号**：010 (`btc_15m_moneyflow`)
- **执行框架**：NautilusTrader 15m 事件驱动撮合引擎 (100% Causal)
- **回测区间**：2023-01-01 至 2025-12-31 (36 个月完整牛熊周期)
- **摩擦模型**：5 bps 悲观滑点 + Binance/OKX 双交易所真实费率 + 同 bar 触及止盈止损优先判定止损
- **详细交易明细**：矩阵中所有 10 组实验的每笔交易均独立存储在 `reports/trade_records_matrix/` 目录下。

---

## 一、基准组 (BTC 5x 永续, $10K 本金, Binance) 真实回测全貌

- **累计成交笔数**：**748 笔**（平均每 2.5 天成交 1 笔，符合中频波段定位）
- **策略胜率**：**30.35%**
- **订单成交结构**：
  - 止盈限价单成交 (TP): **154 笔** (享受 Maker 0.02% 费率)
  - 止损市价单成交 (SL): **480 笔** (承受 5 bps 滑点与 Taker 费率)
  - 4小时超时市价平仓: **114 笔**
- **累计净收益率**：**-98.06%**
- **年化复合收益率 (CAGR)**：**-73.13%**
- **最大动态回撤 (MDD)**：**98.08%**
- **年化夏普比率 (Sharpe)**：**-6.12**
- **卡尔玛比率 (Calmar)**：**-0.75**

---

## 二、开平仓规则与交易属性规范

所有交易记录严格遵照以下规则执行并在 CSV 中逐笔留痕：
1. **开仓规则 1 (`RULE_1_LONG_SWEEP_OFI_ABSORPTION`)**:
   - `Low[t] <= SwingLow48[t]` 且 `Close[t] > SwingLow48[t]` (流动性扫荡拒绝探底回升)
   - `OFI[t] > -0.05` (买盘吸收) 且 `Vol_Compression[t] < 1.15`
   - 下一根 bar 开盘价以市价买入，滑点 5 bps
2. **开仓规则 2 (`RULE_2_SHORT_SWEEP_OFI_ABSORPTION`)**:
   - `High[t] >= SwingHigh48[t]` 且 `Close[t] < SwingHigh48[t]` (流动性扫荡拒绝冲高回落)
   - `OFI[t] < 0.05` (卖盘吸收) 且 `Vol_Compression[t] < 1.15`
   - 下一根 bar 开盘价以市价做空，滑点 5 bps
3. **平仓规则**:
   - `TP_LIMIT_HIT`: 触及 $Entry \pm 2.2 	imes ATR_14$ 限价止盈 (Maker 费率)
   - `SL_STOP_HIT`: 触及 $Entry \mp 1.2 	imes ATR_14$ 市价止损 (Taker 费率 + 滑点)
   - `SL_PESSIMISTIC_COLLISION`: 同 bar 内高低点同时满足止盈和止损时，保守判定止损生效
   - `TIME_EXIT_4H`: 持仓满 16 根 K 线（4 小时）按收盘价平仓

---

## 三、各参数矩阵回测报告一览

详见 [MULTI_ASSET_MATRIX.md](./MULTI_ASSET_MATRIX.md) 与 [CREDAL_EVIDENTIAL_ANALYSIS.md](./CREDAL_EVIDENTIAL_ANALYSIS.md)。
每组实验的独立交易文件见：
- BTC 基准组: [`trades_asset_BTC_5x_10k_binance.csv`](./trade_records_matrix/trades_asset_BTC_5x_10k_binance.csv)
- ETH 标的组: [`trades_asset_ETH_5x_10k_binance.csv`](./trade_records_matrix/trades_asset_ETH_5x_10k_binance.csv)
- SOL 标的组: [`trades_asset_SOL_5x_10k_binance.csv`](./trade_records_matrix/trades_asset_SOL_5x_10k_binance.csv)
- XAU 黄金组: [`trades_asset_XAU_5x_10k_binance.csv`](./trade_records_matrix/trades_asset_XAU_5x_10k_binance.csv)
- USO 原油组: [`trades_asset_USO_5x_10k_binance.csv`](./trade_records_matrix/trades_asset_USO_5x_10k_binance.csv)
- BTC 3x 杠杆: [`trades_btc_lev_3x_10k_binance.csv`](./trade_records_matrix/trades_btc_lev_3x_10k_binance.csv)
- BTC 10x 杠杆: [`trades_btc_lev_10x_10k_binance.csv`](./trade_records_matrix/trades_btc_lev_10x_10k_binance.csv)
- BTC $1K 本金: [`trades_btc_capital_1000_5x_binance.csv`](./trade_records_matrix/trades_btc_capital_1000_5x_binance.csv)
- BTC $100K 本金: [`trades_btc_capital_100000_5x_binance.csv`](./trade_records_matrix/trades_btc_capital_100000_5x_binance.csv)
- BTC OKX 费率: [`trades_btc_exchange_okx_5x_10k.csv`](./trade_records_matrix/trades_btc_exchange_okx_5x_10k.csv)
- 样本内 (IS): [`trades_btc_IS_2023_2024.csv`](./trade_records_matrix/trades_btc_IS_2023_2024.csv)
- 样本外 (OOS): [`trades_btc_OOS_2025.csv`](./trade_records_matrix/trades_btc_OOS_2025.csv)
- WFO 2023 年: [`trades_btc_wfo_year_2023.csv`](./trade_records_matrix/trades_btc_wfo_year_2023.csv)
- WFO 2024 年: [`trades_btc_wfo_year_2024.csv`](./trade_records_matrix/trades_btc_wfo_year_2024.csv)
- WFO 2025 年: [`trades_btc_wfo_year_2025.csv`](./trade_records_matrix/trades_btc_wfo_year_2025.csv)
- 随机窗口 A: [`trades_btc_wfo_random_winA.csv`](./trade_records_matrix/trades_btc_wfo_random_winA.csv)
- 随机窗口 B: [`trades_btc_wfo_random_winB.csv`](./trade_records_matrix/trades_btc_wfo_random_winB.csv)
