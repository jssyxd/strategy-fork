# NautilusTrader 多策略实盘部署集群与监控看门狗体系 (Multi-Strategy Live Cluster)

![Status](https://img.shields.io/badge/status-LIVE%20CLUSTER%20ACTIVE-brightgreen.svg)
![Mode](https://img.shields.io/badge/mode-OKX%20Demo%20Simulated-blue.svg)
![Nautilus](https://img.shields.io/badge/framework-NautilusTrader%20v1.221-blue.svg)
![Timer](https://img.shields.io/badge/cron-15%20Minutes%20Active-green.svg)

本目录归档了官方 **多策略 NautilusTrader 实盘集群部署方案**。
所有 6 大核心量化策略均已完成独立微服务与容器化封装，配置了已从 NFS 密钥库领取的 OKX 模拟盘真实接入凭证，且本地守护进程与 15 分钟系统定时巡检均已激活运行。

---

## 一、 部署的 6 大量化实盘策略服务矩阵

| 服务代号 | 策略全称 | 标的合约 | 时序周期 | 核心决策机制 | 进程 PID |
| :--- | :--- | :---: | :---: | :--- | :---: |
| `01_eth_dynamic` | **012 ETH 15m 事件驱动动态 Q-State** | `ETH-USDT-SWAP` | 15m | 涌现 IIR 低通平滑 + 动态追踪止盈 + 2% 止损 | 437457 |
| `02_smc_adaptive` | **005 SMC 多资产自适应趋势回踩** | `BTC-USDT-SWAP` | 15m | 狄利克雷证据门控 ($u \le 0.35, C \le 0.40$) + LightGBM 宏观状态 | 437471 |
| `03_as_grid` | **012 AS 微观高频做市网格** | `BTC-USDT-SWAP` | 1m | 随机控制保留价格倾斜 + L2 盘口毒性避险撤单 | 437484 |
| `04_nd100_enh` | **004 QQQ 纳指动量期权增强** | `BTC-USDT-SWAP` | 1H | 20日动量过滤 + 备兑看涨贴息增厚 + 保护性看跌期权 | 437501 |
| `05_doge_carry` | **008 DOGE 动量 Carry 双核** | `DOGE-USDT-SWAP` | 15m | Garman-Klass 波动率分位数门控 + 8h 资金费率对冲 | 437515 |
| `06_eth_squeeze` | **009 ETH 波动率压缩破位** | `ETH-USDT-SWAP` | 1H | 布林带脱离肯特纳通道 Gamma 挤压破位 | 437531 |
| `watchdog` | **顶级量化机构 AI 哨兵自愈看门狗** | ALL | 60s | 实时检查连续止损、胜率衰减、波动率翻倍并调度 Kaggle | 437855 |

---

## 二、 凭证领用与数据血缘声明

- **凭证源文件**: `nfs://admin@192.168.1.6/fs/1000/nfs/iflow/bybitAPIkeys.txt`
- **领用记录**: 已选取未被占用的 `demo2` 秘钥，并在 NFS 原文档中成功追加持久化标注：
  > `2026年10月25日 16时35分，当前多策略NautilusTrader实盘集群(012/005/012_avellaneda/004/008/009)在使用apikey c0020735-b707-4084-9718-d3dd68173ebd 交易`
- **账户环境**: OKX 模拟交易环境 (`x-simulated-trading: 1`)，当前总净值 \$98,248.70 USD。

---

## 三、 监控 Watchdog 哨兵体系与 Kaggle 重训触发机制

看门狗 `watchdog_trader_sentinel.py` 严格落实《量化投研宪法》中的 5 项核心风控门槛：

1. **增量演化时间窗口 (TRG-TIMER-2M)**：
   自上次训练起满 60 天（2个月），调度 Kaggle 云端算力执行长时序增量演化；
2. **出厂冷冻期保护 (Freeze Period)**：
   新上线模型在样本外必须无人工干预运行 30~60 天，检验实盘表现与回测胜率的一致性；
3. **宏观波动率机制跃迁 (TRG-VOL-EXP)**：
   以太坊近 14 天日均振幅（ATR）发生翻倍放大（如从 2% 飙升至 5%+），原有极值通道失效，阻断开仓并重训；
4. **统计失效率触发 (TRG-DEFICIT)**：
   实盘连续出现 3 笔硬止损亏损，或近 30 笔滚动胜率跌破 60%（基准预期 70%~85%），立即市价清仓并冷冻 48 小时；
5. **流动性损耗与滑点加剧 (TRG-SLIP-EROSION)**：
   实盘滑点摩擦损耗吞噬单笔利润超过 40%，自动将开仓规模减半并拉宽挂单距离。

### 自动化云端调度 (GitHub Actions & Kaggle CLI)
- 工作流文件：`.github/workflows/watchdog_kaggle_retrain.yml`
- 触发方式：支持定周期（每月 1 日与 15 日）、GitHub Webhook、`repository_dispatch` 及本地看门狗直调 Kaggle CLI。

---

## 四、 15 分钟系统级健康巡检与异常自动报告 (Cron Inspector)

系统已通过 Native Systemd User Timer 配置了每 15 分钟自动化巡检任务：
- **执行命令**: `/home/da/.venvs/quant/bin/python deploy_cluster/cron_15m_inspector.py`
- **触发定时器**: `systemd --user list-timers nautilus-inspector.timer` (执行周期 `*:0/15`)
- **自动巡检产出**: 实时更新 `deploy_cluster/TRADING_ALERT_REPORT.md` 与项目根目录 `TRADING_ALERT_REPORT.md`
- **巡检核查项**:
  - 各进程心跳是否在过去 120 秒内更新（防卡死/网络异常）；
  - 检查 OKX 接口是否有 51008（保证金不足）、401（签名过期）、429（频控报警）；
  - 校验各策略核心逻辑偏离度（如网格库存超标、假突破过滤等）。

---

## 🛠 本地运维与控制指南

```bash
# 1. 查看集群运行状态
python deploy_cluster/cluster_manager.py status

# 2. 启动全量策略集群与看门狗
bash deploy_cluster/start_cluster.sh

# 3. 停止全量策略集群
bash deploy_cluster/stop_cluster.sh

# 4. 手动执行一次 15 分钟健康巡检
python deploy_cluster/cron_15m_inspector.py

# 5. Docker 容器化启动 (当宿主机 Docker 服务开启后)
cd deploy_cluster && docker compose up -d
```
