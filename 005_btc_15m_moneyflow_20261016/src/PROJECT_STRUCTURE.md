# 项目文件结构：btc_15m (加密货币 15 分钟高频量化回测与波段系统)

> **根路径**：`~/btc_15m`（终端提示符 `trader@localhost:~/btc_15m$`）  
> **核心标的**：Binance / XT.com `BTC/USDT` 15 分钟 K 线  
> **核心指标**：`dt_vix ABIEE (Calmar): 8.68`，累计收益显著跑赢 Nasdaq ETF 基准  
> **技术栈**：Python 3.9.6, Matplotlib, Pandas

---

## 1. 目录树形结构

```
btc_15m/
├── swing.py                     # 波段策略执行脚本（终端运行：python3 swing.py）
├── softbox.py                   # 回测性能统计与指标导出脚本
├── YAND.py                      # YAND 策略主实现与累计收益计算（2026-05-01 保存）
├── nasdaq.py                    # Nasdaq ETF (S&P 500) 基准对比与 Matplotlib 可视化
│
├── ── 回测统计与明细报告 ──
├── strategy_statistics.txt      # 策略回测统计摘要（包含 Calmar: 8.68 等指标）
├── strategy_trade_records.csv   # 逐笔交易记录明细（时间戳、买卖动作、成本、收益）
│
└── ── 资金流向高频监控数据 ──
    ├── moneyflow_summary_20260414_2035.csv   # 2026-04-14 20:35 资金流入/流出汇总
    ├── moneyflow_summary_20260415_2035.csv   # 2026-04-15 20:35 资金流入/流出汇总
    └── moneyflow_summary_20260416_2035.csv   # 2026-04-16 20:35 资金流入/流出汇总
```

---

## 2. 模块职责说明表

| 文件名 | 职责说明 | 关联视频内容 |
|---|---|---|
| `swing.py` | 波段交易主入口脚本 | 终端以 `python3 swing.py` 执行，打印 Calmar 8.68 |
| `softbox.py` | 回测指标生成与文本输出 | 代码中写入 `strategy_statistics.txt` 并格式化打印 |
| `YAND.py` | 策略收益曲线运算核心 | 标签页提示 `File Saved - May 1, 2026 at 1:27 PM` |
| `nasdaq.py` | 绘制基准对比图表 | Matplotlib 绘制 `Backtest: Nasdaq ETF vs AI Strategy` |
| `strategy_statistics.txt` | 文本指标摘要 | 底部通知反复提示该文件已更新 |
| `moneyflow_summary_*.csv` | 资金净流向监控文件 | Explorer 面板展开的高频监控时间序列 |
