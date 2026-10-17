# 方案总览与设计原则

## 问题背景

主账户策略在 2026-10-05 至 10-09 期间取得显著正收益（约 +79 USDT，小资金高收益率），但 10 月 9 日及之后使用完全相同参数产生严重亏损。肉眼观察主流加密标的 K 线并无 2025-10-11 级别黑天鹅，属于典型的 **市场 Regime 切换**（从干净趋势+回踩环境切换到清算后高噪声/假突破环境）。

Demo 账户（风险 1%、初始约 95k）覆盖更长时间（10-02 至 10-15），共 127 次开仓 / 125 次平仓，总 PnL 约 +11,372 USDT，胜率约 41.6%，同样在 10-09 出现明显回撤后恢复。

## 解决思路

不做“每日连续优化十几个浮点参数”（极易过拟合），而是：

1. 定义 3~4 个**离散模式**（TrendFollow / HighSelectivity / Invert / NoTrade）。
2. 用 LightGBM / XGBoost 做 **Regime → 模式** 的分类器。
3. 严格 Purged Walk-Forward 验证。
4. 模式切换设置置信度门槛 + 安全闸门 + 可审计热更新。

## 离散模式定义（初版）

| 模式 | 行为描述 | 适用场景 |
|------|----------|----------|
| TrendFollow | 原策略逻辑（或轻微提高门槛） | 趋势清晰、回踩质量高、低冲突 |
| HighSelectivity | 大幅提高 min_score / 收紧 u/C / 降低风险比例 | 趋势尚在但噪声增加 |
| Invert | 信号方向反转 + 调整止损止盈逻辑 | 明确震荡/假突破主导期 |
| NoTrade | 停止开仓或只允许极高置信度 | 高冲突、清算后遗症、波动异常 |

## 推荐 Kaggle 参考

- 主骨架：https://www.kaggle.com/code/marketneutral/purged-time-series-cv-xgboost-optuna
- Regime 补充：https://www.kaggle.com/code/digantabhattacharya/drw-xgboost-lgbm-regimes-baseline-model
- 严格多路径：https://www.kaggle.com/code/gogo827jz/combinatorial-purged-group-k-fold

## 与仓库 anti/ 宪法对齐

本方案强制执行：
- 无未来函数
- Purged + Embargo
- 真实交易日志优先
- 所有变更可审计
