# 量化策略回测与动态重训生产环境部署指南
## Backtest Environment Preparation & Governance Specification

本指南归档了 `strategy-fork` 策略集群进行 **高保真 NautilusTrader L2 回放回测、2 年 20 轮滚动重训、Kaggle 云端算力调度与 AI 哨兵监控** 所必需的完整环境与数据依赖。

---

### 一、 必备环境与软件依赖

#### 1. Python 运行环境与核心包矩阵
推荐使用已配置的专用虚拟环境 `/home/da/.venvs/quant/bin/python`：

| 软件包 | 最低版本要求 | 用途与定位 |
| :--- | :--- | :--- |
| **Python** | `3.11.x` / `3.13.x` | 基础解释器（支持最新 Type Hint 与 GIL 优化） |
| **NautilusTrader** | `1.221.0` | 纳秒级事件驱动回测引擎，支持 L1/L2/L3 订单簿回放 |
| **PyArrow** | `>= 15.0.0` | 生产级 Parquet 零拷贝内存映射与列式读取 |
| **LightGBM** | `>= 4.3.0` | SMC ML 自适应状态分类与因子排序 |
| **Pandas / NumPy** | `pandas>=2.2.0`, `numpy>=1.26.0` | 向量化数据处理与矩阵运算 |
| **Numba** | `>= 0.59.0` | Avellaneda-Stoikov 高频微观做市内核 JIT 加速 |
| **Kaggle CLI** | `>= 1.6.0` | 远程无缝推送 GPU/TPU 训练任务与下载 Checkpoint |

一键验证脚本：
```bash
/home/da/.venvs/quant/bin/python -c "
import nautilus_trader, pyarrow, pandas, lightgbm, numba
print('NautilusTrader:', nautilus_trader.__version__)
print('All core dependencies loaded successfully.')
"
```

---

### 二、 必备数据依赖与存储血缘

本地高速数据湖与局域网万兆 NFS 存储池已完成双向校验与同步：

#### 1. 存储路径定义
- **本地 NVMe 主存储**：`/home/da/桌面/database/`
- **局域网万兆 NFS 镜像**：`nfs://admin@192.168.1.6/fs/1000/nfs/iflow/backtestTools/data/`（挂载至 `/mnt/iflow/backtestTools/data/`）

#### 2. 已治理的高频 L2/L3 订单簿与时序数据清单
所有数据均通过 `dataBaseLake` 五大数学不变量验证（单调自增、去重、价格大于零、无虚构插值）：

```text
03_governed_lake/v2_parquet_lake/crypto/high_frequency_lob/
├── BTCUSDT/
│   ├── BTCUSDT_1m_3years_governed.parquet       # 3年全周期 1,636,229 根已治理 1m K线
│   ├── BTCUSDT_trades_20260418_governed.parquet # 1,941,077 笔严格单调逐笔成交流 (Tick)
│   ├── BTCUSDT_snapshots_20260418_governed.parquet # 1,434 组 L2 深度盘口快照
│   └── BTCUSDT_depth20_20260326_governed.parquet   # 322,674 组 100ms 频率 Depth20 盘口
└── ETHUSDT/
    └── ETHUSDT_depth20_20260326_governed.parquet   # ETH 100ms L2 深度盘口
```

---

### 三、 Kaggle 云端 GPU/TPU 调度凭证配置

系统通过本地 Watchdog 看门狗与重训引擎直调 Kaggle 云端资源：
- **Token 凭证**：`KGAT_ac40707589c873af896d44997f6c0d40`
- **环境变量导出**：
  ```bash
  export KAGGLE_API_TOKEN="KGAT_ac40707589c873af896d44997f6c0d40"
  ```
- **云端训练结果与 Notebook 归档规范**：
  所有调用 Kaggle 训练的脚本、元数据与生成的 Checkpoint 统一存放在 `kaggle_experiments/` 对应子目录内：
  - `kaggle_experiments/strategy_1_smc/`
  - `kaggle_experiments/strategy_2_avellaneda/`
  - `kaggle_experiments/strategy_3_eth_alphaevolve/`

---

### 四、 核心工作流运行指令

#### 1. 执行 2 年 20 轮滚动重训与回测套件
切片规格：5,000 根 K 线（2,500 根样本内训练 / 2,500 根样本外盲测），步长 2,500 根：
```bash
cd /home/da/桌面/ml-learning/strategy-fork
/home/da/.venvs/quant/bin/python kaggle_experiments/run_rolling_experiments.py
```

#### 2. 执行策略 004、005、006 综合工作流
```bash
/home/da/.venvs/quant/bin/python kaggle_experiments/workflow_004_005_006.py
```

#### 3. 运行多 Agent 因子挖掘流水线
- AlphaGPT 符号 AST 挖掘：`kaggle_experiments/factor_mining/alphagpt/`
- Qlib 正交特征库与 IC/IR 检验：`kaggle_experiments/factor_mining/qlib/`
- 微软 RD-Agent 交叉对账引擎：`kaggle_experiments/factor_mining/rd_agent/`
