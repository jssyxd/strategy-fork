# 项目文件结构：options_hedging_system (深度学习期权对冲与实时交易系统)

> **根路径**：`options_hedging_system/`  
> **语言与框架**：Python 3.9.6, PyTorch (`nn.TransformerEncoder`), Pandas, NumPy  
> **核心模型**：`VolatilityTransformer`、`DeepDatedgingOptimizer`、`ChipEngine`  
> **运行模式**：`REAL_TRADING`（实盘交易模式，向交易所 API 发送 HTTP POST 订单）

---

## 1. 目录树形结构

```
options_hedging_system/
├── __init__.py                  # 包入口初始化
├── config.py                    # 系统全局配置（超参数、CNN 通道、宏观资产池）
├── main.py                      # 系统主入口
├── orchestrator.py              # 全局组件调度器
│
├── ── 模型与核心计算 ──
├── deep.py                      # 深度学习底层网络模块
├── transformer.py               # VolatilityTransformer（波动率/相关性/CVaR 预测）
├── engine.py                    # DeepDatedgingOptimizer（深度对冲优化器）
├── pretrain.py                  # 预训练脚本（PRETRAIN_EPOCHS = 15）
├── finetune.py                  # 微调脚本（模型微调并保存至 arm_weights.pt）
├── model_eze.py                 # 模型推理封装与 ChipEngine 筹码计算引擎
├── best_model.pth               # 训练得到的 PyTorch 最优模型权重文件
│
├── ── 策略与执行层 ──
├── strategy.py                  # 期权策略状态机（IronCondor / Straddle / 仓位比例管理）
├── executor.py                  # 订单执行器（REAL_TRADING POST HTTP 订单发送）
├── realtime_engine.py           # 实时引擎主循环（驱动数据流 -> 预测 -> 策略决策）
├── stream_parser.py             # 行情 WebSocket 数据流解析器（含 Ozymandias 标识）
├── vthe.py                      # 策略衍生变体模块
├── vanogy.py                    # 策略辅助逻辑模块
│
├── ── 数据与基建层 ──
├── data_manager.py              # 数据校验与管道管理
├── chip_tushare.py              # Tushare A 股筹码数据获取（cyq 筹码分布）
├── diagnose_chip_source.py      # 筹码数据质量诊断（winner_rate / weight_avg 检验）
├── download_xt_history.py       # XT.com 交易所历史 15m K 线数据下载
├── trading_fees.py              # 交易手续费与滑点成本计算（Binance/XT 费率）
├── infra.py                     # 基础工具库（np.isfinite 数值安全校验等）
│
├── ── 缓存与持久化数据 ──
├── biz_desc_cache.json          # 标的股票/代币业务描述信息缓存
├── chip_cache.json              # 筹码指标计算结果本地缓存
├── news_cache.json              # 新闻资讯文本缓存
├── sentiment_cache.json         # 市场情感分析打分缓存
├── alpha_trader.log             # 实时交易日志（包含 HTTP POST 下单记录）
│
├── ── 子目录 ──
├── trades/                      # 训练权重与交易输出目录
│   └── arm_weights.pt           # 模型检查点权重文件
└── chip_reports/                # 筹码诊断分析报告目录
    └── chip_diagnose_20260409.json  # 历史筹码源诊断报告
```

---

## 2. 模块职责说明表

| 文件名 | 角色与层级 | 核心职责 |
|---|---|---|
| `transformer.py` | 模型层 | 构建基于自注意力机制的 VolatilityTransformer，预测 `pred_vol`、`pred_corr`、`pred_cvar` |
| `engine.py` | 计算层 | `DeepDatedgingOptimizer` 对冲计算，依据期权数据库动态调整 Delta/Gamma 并最小化总交易成本 |
| `strategy.py` | 策略层 | 维护期权策略状态机（根据置信度阈值 0.60/0.51 切换 Straddle 与 IronCondor） |
| `executor.py` | 执行层 | 封装交易所 API 通信，向交易服务发送实盘 HTTP POST 下单请求 |
| `stream_parser.py` | 数据流层 | 实时解析 WebSocket 行情推流，清洗价格与成交量 |
| `chip_tushare.py` | 特征工程 | 接入 Tushare Pro 接口提取 A 股个股获利比例、平均成本等筹码特征 |
| `infra.py` | 底层基建 | 验证特征数值有限性，防止 NaN/Inf 污染深度模型前向传播 |
| `config.py` | 配置层 | 统一定义宏观资产、膨胀卷积参数 `CMDILATION = [1, 2, 4, 8]` 及模型路径 |
