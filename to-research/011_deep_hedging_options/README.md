# 策略 011：深度学习期权做市与 Delta-Gamma 对冲 (DeepHedging)

- **策略编号**：011
- **策略名称**：`deep_hedging_options`
- **首次部署日期**：待回测（逆向复刻目标，尚未部署）
- **运行环境**：Python 事件驱动实盘 + Docker 部署，支持 REAL_TRADING 模式
- **交易品种**：XT.com 加密期权 + A股筹码微观结构
- **执行时间框架**：分钟级 / 事件驱动
- **逆向源码完备度**：**A 级**（A=录屏爬取完整源码；B=公开仓库含核心策略文件；C=仅通用基建/理论推导 + 本地推导实现）

---

## 一、官方结果定义（逆向研发成功的最终约束）

> 数据来源：春江智能官方网站 **https://www.chunjiang.dev/** （抓取时间 2026-10-07）。
> **本节指标为逆向研发的“成功定义”与“最终约束”**：只有在指定回测口径下复现下列指标（容差内），并同时通过样本外/滚动验证，方判定该策略逆向研发成功。

**官方未以独立“交易策略”条目公布本系统结果定义。** 本策略源自《那就好好道个别吧》录屏工程 `hwenithe_risk`。其技术栈与官网 `机构卖方服务系统`（“可解释期权定价（Thales，谱球面优化器）+ 高频执行 + 容量测算”）**同源**，可作为能力对齐目标：

| 官方母项（机构卖方服务系统） | 官方取值 |
| :--- | :--- |
| 策略方向 | 机构级算法执行与风控套件 |
| 核心方法 | Looped Transformer 微观订单流拆单 & 谱球面优化器定价 |
| 适用领域 | 资管机构与券商自营高频执行 |
| 滑点控制 | 极低水平 |

**逆向研发成功的定义（最终约束）**：以录屏实盘证据为准 —— 完整实现 `REAL_TRADING` 事件流、VolatilityTransformer 三任务预测（vol / corr / cvar）、`DeepDatedgingOptimizer` 对冲优化与 IronCondor/Straddle 状态机，并通过 Docker 冷启动即可实盘下单（账户状态与交易所真实净持仓一致）。

---

## 二、策略核心机制与数学原理

1. **VolatilityTransformer**：`feature_size=30 / d_model=28 / 3 层`，联合输出波动率、相关性、CVaR，损失 `L = 1.0·L_vol + 0.5·L_corr + 1.0·L_var`。
2. **DeepDatedgingOptimizer**：以 `holdings` + `options_db` 计算最优先对冲标的与手数，最小化残余 Delta/Gamma 并惩罚交易成本。
3. **期权多腿状态机**：预测概率 ≥0.60 买入跨式；≥0.51 卖出铁鹰；逆转时平仓保护。
4. **筹码引擎 ChipEngine**：获利盘比例、加权成本、集中度辅助现货趋势判断。

---

## 三、逆向源码现状（完备度 A 级）

### 3.1 已落地源码
录屏视频爬取的完整源码：
- `transformer.py`、`engine.py` / `deep.py`、`strategy.py`、`model_eze.py`
- `realtime_engine.py`、`executor.py`、`stream_parser.py`、`chip_tushare.py`、`diagnose_chip_source.py`、`download_xt_history.py`
- `trading_fees.py`、`infra.py`、`deploy/`（Dockerfile + docker-compose.yml）、`PROJECT_STRUCTURE.md`

### 3.2 已移出的非策略基建
无（本策略源码直接来自录屏）。

---

## 四、待完成的回测与验收方案

1. **数据**：按交易品种接入对应历史数据（含手续费/滑点）。
2. **回测口径**：与官方 分钟级 / 事件驱动 频率对齐，计入真实成本。
3. **验收**：上述“逆向研发成功的定义”表格逐项通过；并通过 Walk-Forward（WFE ≥ 60%）与蒙特卡洛压力测试。
4. **样本外**：至少 6 个月样本外盲测，样本外指标不得劣化超过 30%。

---

## 五、缺失部分与继续深入研究方向

- **缺失**：机构级跨标的动态组合保证金借贷利息优化模型；毫秒级全市场期权无套利曲面标定。
- **深入**：将 Python 端事件循环迁移至 `Moses` C++ Boost.Asio 异步网络层以承接万级并发 Tick。

---

## 六、实盘避坑预置（继承本仓库通用工程规范）

> 待回测通过、进入实盘阶段后，须逐条对齐本仓库 `001_smc_matrix_20260930/README.md` 第三节已归档的五大工程级事故规范：
> ① 客户端订单 ID 格式与 `on_order_denied` 全生命周期；② 冷启动历史 K 线 REST 预热；③ 平仓单强制 `reduce_only` + 净持仓绑定 + 看门狗接管；④ 限价单 TTL 撤单防逆向选择；⑤ 连续亏损熔断的冷却自动解封。
