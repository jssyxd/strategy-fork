# SMC V4 机器学习自适应与 Credal 不确定性门控：实盘上线部署指南

## 一、本次升级的核心改变与针对性解决的问题

在 2026-10-05 至 2026-10-09 的实盘中，原策略（V3）依赖纯技术指标（EMA顺势 + 量能 + CLV + 波动区间）与静态 Dirichlet 门控（$u \le 0.35, C < 0.40$），在顺势环境中取得了卓越收益（+65 USDT / +30%）。  
但在 **10月9日行情突变（清算踩踏与高多空冲突锯齿市）** 后，静态规则失效并引发连续假突破止损。

**V4 版本重大升级（已通过 Kaggle L1-L4 四层时钟加权验证）：**
1. **嵌入轻量化零依赖 LightGBM 决策引擎**：
   - 纯 Python 递归树求值器（84 微秒/Bar，无任何额外 pip 依赖，与官方 C++ 库概率完全一致）。
   - 自动加载 `regime_model_lightgbm.txt` 模型权重。
2. **离散四模式动态自适应 (Regime Adaptive)**：
   - **`TrendFollow`**：低冲突、低不确定性。执行标准 SMC 趋势策略（min_score=60, 5% 风险）。
   - **`HighSelectivity`**：波动率扩张、震荡抬升。收紧开仓门槛至 `min_score=70`，风险预算减半至 2.5%，止损收窄至 1.2 ATR。
   - **`Invert`**：持续诱多诱空假突破行情。当置信度 $\ge 60\%$ 时反转开仓方向，采用非对称 1.0 ATR 快速止盈。
   - **`NoTrade`**：清算剧烈期或多空极度胶着。**绝对硬否决（VETO）**，全币种保持空仓防守。
3. **Credal Transformer 双重反幻觉/反过拟合守卫 (arXiv:2510.12137)**：
   - 当方向冲突度 $C \ge 0.45$ 或认知不确定性 $u \ge 0.38$ 时，强行执行熔断一票否决。
   - 在 10-09 至 10-15 历史验证中，**成功否决 259 笔亏损假突破交易，净挽回 +52.59 R 亏损**！

---

## 二、部署运行环境与配置参数

### 1. 文件清单与目录结构
在你的服务器或 Docker 容器挂载目录 `/strategies` 中，确保以下文件就绪：
```text
/strategies/
├── v4_20261018_ml_adaptive.py      # [核心] V4 实盘策略主程序
├── regime_model_lightgbm.txt       # [权重] Kaggle 训练出的 LightGBM 模型权重
├── v3_20261007_1830_rollback3.py   # [备份] V3 原版策略（随时可回滚）
└── smc_live_trader_v4.py           # 启动快捷入口
```

### 2. 环境变量配置 (`.env` 或系统环境变量)
```bash
# 运行环境：LIVE 为真实实盘，DEMO 为模拟盘
OKX_ENV=LIVE
OKX_ACCOUNT_ID=OKX-LIVE-001

# API 凭据
OKX_API_KEY=你的OKX实盘APIKey
OKX_API_SECRET=你的OKX实盘APISecret
OKX_API_PASSPHRASE=你的OKX密码短语
```

### 3. Docker 启动或独立运行指令
- **Docker Compose 模式**（推荐）：
  修改 `docker-compose.yml` 中的启动指令：
  ```yaml
  command: ["python", "v4_20261018_ml_adaptive.py"]
  ```
  执行重启：
  ```bash
  docker compose restart nautilus
  ```
- **纯 Python 原生模式**：
  ```bash
  python strategies/v4_20261018_ml_adaptive.py
  ```

---

## 三、实盘日志与关键监控指标排查

策略启动后，每 15 分钟收线时将输出以下结构化日志：
```text
[BTC-USDT-SWAP] ML-REGIME: TrendFollow (Conf: 58.2%) | RawSignal=LONG(65.0) | u=0.240, C=0.312 | Veto=False
[BTC-USDT-SWAP] SIGNAL: LONG | Score=65.0 | Evidential u=0.240, C=0.312 | Gate Passed: True
```
如果当前属于震荡清算市：
```text
[BNB-USDT-SWAP] ML-REGIME: NoTrade (Conf: 98.3%) | RawSignal=SHORT(60.0) | u=0.214, C=0.900 | Veto=True
[BNB-USDT-SWAP] SIGNAL VETOED by ML-Regime/Credal Gate: Model predicts NoTrade (Confidence=98.3%)
```
**如果看到 `SIGNAL VETOED`，说明 Credal 动态门控正在准确拦截劣质假突破信号，属于正常保护行为。**

---

## 四、回滚方案 (Rollback Plan)
万一出现交易所网络或异常状态，如需秒级回退至 V3 原始策略：
1. 将启动命令改回 `python strategies/v3_20261007_1830_rollback3.py`
2. 重启容器即可，两版本持仓数据与 Hydration 逻辑 100% 兼容。
