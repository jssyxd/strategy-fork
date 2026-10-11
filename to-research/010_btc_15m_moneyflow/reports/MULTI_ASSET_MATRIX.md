# 多资产、多杠杆与多资金规模真实回测矩阵报告 (NautilusTrader)

> 本报告汇总了基于 15m 资金流失衡与微观流动性扫荡吸收策略在 2023-2025 年无任何人工合成干预下的真实事件驱动回测数据。每组实验均已生成独立交易记录 CSV 文件存放在 `reports/trade_records_matrix/` 目录下。

## 一、真实多资产横截面与参数矩阵

| 实验代号 | 标的 | 杠杆 | 本金 | 交易所 | 真实笔数 | 真实胜率 | 累计收益率 | 最大回撤 | 夏普比率 | 卡尔玛 | TP限价笔数 | SL止损笔数 | 超时平仓 | 交易明细文件 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `asset_BTC_5x_10k_binance` | **BTC** | 5.0x | $10,000 | BINANCE | **748** | **30.35%** | **-98.06%** | **98.08%** | **-6.12** | **-0.75** | 154 | 480 | 114 | [`trades_asset_BTC_5x_10k_binance.csv`](./trade_records_matrix/trades_asset_BTC_5x_10k_binance.csv) |
| `asset_ETH_5x_10k_binance` | **ETH** | 5.0x | $10,000 | BINANCE | **781** | **33.8%** | **-94.52%** | **95.83%** | **-4.62** | **-0.65** | 179 | 484 | 118 | [`trades_asset_ETH_5x_10k_binance.csv`](./trade_records_matrix/trades_asset_ETH_5x_10k_binance.csv) |
| `asset_SOL_5x_10k_binance` | **SOL** | 5.0x | $10,000 | BINANCE | **881** | **34.17%** | **-89.25%** | **90.07%** | **-3.11** | **-0.58** | 231 | 543 | 107 | [`trades_asset_SOL_5x_10k_binance.csv`](./trade_records_matrix/trades_asset_SOL_5x_10k_binance.csv) |
| `asset_XAU_5x_10k_binance` | **XAU** | 5.0x | $10,000 | BINANCE | **498** | **17.27%** | **-98.67%** | **98.67%** | **-8.89** | **-0.77** | 76 | 383 | 39 | [`trades_asset_XAU_5x_10k_binance.csv`](./trade_records_matrix/trades_asset_XAU_5x_10k_binance.csv) |
| `asset_USO_5x_10k_binance` | **USO** | 5.0x | $10,000 | BINANCE | **494** | **27.53%** | **-96.53%** | **96.63%** | **-5.51** | **-0.7** | 103 | 333 | 58 | [`trades_asset_USO_5x_10k_binance.csv`](./trade_records_matrix/trades_asset_USO_5x_10k_binance.csv) |
| `btc_lev_3x_10k_binance` | **BTC** | 3.0x | $10,000 | BINANCE | **748** | **30.35%** | **-95.81%** | **95.86%** | **-5.57** | **-0.68** | 154 | 480 | 114 | [`trades_btc_lev_3x_10k_binance.csv`](./trade_records_matrix/trades_btc_lev_3x_10k_binance.csv) |
| `btc_lev_10x_10k_binance` | **BTC** | 10.0x | $10,000 | BINANCE | **748** | **30.35%** | **-98.6%** | **98.6%** | **-6.29** | **-0.77** | 154 | 480 | 114 | [`trades_btc_lev_10x_10k_binance.csv`](./trade_records_matrix/trades_btc_lev_10x_10k_binance.csv) |
| `btc_capital_1000_5x_binance` | **BTC** | 5.0x | $1,000 | BINANCE | **748** | **30.35%** | **-98.06%** | **98.08%** | **-6.12** | **-0.75** | 154 | 480 | 114 | [`trades_btc_capital_1000_5x_binance.csv`](./trade_records_matrix/trades_btc_capital_1000_5x_binance.csv) |
| `btc_capital_100000_5x_binance` | **BTC** | 5.0x | $100,000 | BINANCE | **748** | **30.35%** | **-98.06%** | **98.08%** | **-6.12** | **-0.75** | 154 | 480 | 114 | [`trades_btc_capital_100000_5x_binance.csv`](./trade_records_matrix/trades_btc_capital_100000_5x_binance.csv) |
| `btc_exchange_okx_5x_10k` | **BTC** | 5.0x | $10,000 | OKX | **748** | **29.95%** | **-98.7%** | **98.71%** | **-6.6** | **-0.78** | 154 | 480 | 114 | [`trades_btc_exchange_okx_5x_10k.csv`](./trade_records_matrix/trades_btc_exchange_okx_5x_10k.csv) |

## 二、样本内 (IS) 与样本外 (OOS) 盲测比对

| 数据集划分 | 时间区间跨度 | 真实笔数 | 胜率 | 累计净收益率 | 最大回撤 | 年化夏普 | 交易明细文件 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **In-Sample (IS)** | 2023-01-01 至 2024-12-31 (24m) | **478** | 32.43% | -89.12% | 89.25% | -5.27 | [`trades_btc_IS_2023_2024.csv`](./trade_records_matrix/trades_btc_IS_2023_2024.csv) |
| **Out-of-Sample (OOS)** | 2025-01-01 至 2025-12-31 (12m) | **269** | 26.77% | -81.83% | 81.89% | -7.72 | [`trades_btc_OOS_2025.csv`](./trade_records_matrix/trades_btc_OOS_2025.csv) |

## 三、滚动窗口分析 (Walk-Forward Optimization)

### 1. 自然年切片窗口
| 窗口区间 | 真实笔数 | 胜率 | 累计净收益率 | 最大回撤 | 夏普比率 | 卡尔玛 | 交易明细文件 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **2023 自然年** | **205** | 32.68% | -64.54% | 64.96% | -5.5 | -1.0 | [`trades_btc_wfo_year_2023.csv`](./trade_records_matrix/trades_btc_wfo_year_2023.csv) |
| **2024 自然年** | **273** | 32.23% | -69.31% | 69.31% | -5.07 | -1.0 | [`trades_btc_wfo_year_2024.csv`](./trade_records_matrix/trades_btc_wfo_year_2024.csv) |
| **2025 自然年** | **269** | 26.77% | -81.83% | 81.89% | -7.72 | -1.0 | [`trades_btc_wfo_year_2025.csv`](./trade_records_matrix/trades_btc_wfo_year_2025.csv) |

### 2. 随机采样滚动窗口
| 采样窗口代号 | 时间区间跨度 | 真实笔数 | 胜率 | 累计净收益率 | 最大回撤 | 夏普比率 | 交易明细文件 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **随机窗口 A** | 2023-05-01 至 2024-04-30 (12m) | **226** | 30.09% | -69.38% | 70.87% | -5.91 | [`trades_btc_wfo_random_winA.csv`](./trade_records_matrix/trades_btc_wfo_random_winA.csv) |
| **随机窗口 B** | 2024-07-01 至 2025-06-30 (12m) | **273** | 30.77% | -75.46% | 76.29% | -6.5 | [`trades_btc_wfo_random_winB.csv`](./trade_records_matrix/trades_btc_wfo_random_winB.csv) |
