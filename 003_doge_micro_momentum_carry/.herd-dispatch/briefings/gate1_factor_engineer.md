# Gate 1 FactorEngineer Agent Briefing
# Role: FactorEngineer — 完成即停，不扩展范围

## 前置条件（Gate0 MUST 已完成）
- `data/silver/doge_aligned_5m.parquet` 已存在
- `data/data_manifest.json` 的 five_invariants_passed = true

## 任务目标
基于 `data/silver/doge_aligned_5m.parquet` 计算全套微观结构因子，
产出 `data/gold/features_5m.parquet` 与 `data/factor_report.json`。

## 约束
- 所有因子计算必须是纯函数：仅使用 [0, t] 历史数据，绝不引用 t+1 及之后数据
- 所有滚动窗口边界严格左闭右闭于 t（包含 t，不包含 t+1）
- 大单阈值必须使用滚动历史分位数（expanding/rolling），禁止用全样本分位数
- 完成即停

## 因子定义（全部确定性纯函数）

### F1: CVD_Z — 累积成交量差背离 Z-Score
```python
# delta_t = taker_buy_volume_t - (volume_t - taker_buy_volume_t)
delta = df['taker_buy_volume'] - (df['volume'] - df['taker_buy_volume'])
cvd = delta.cumsum()
# 滚动 Z-Score，窗口 W1=288 (1天) 和 W2=1440 (5天)
for w in [288, 1440]:
    mu = cvd.rolling(w, min_periods=w//2).mean()
    sigma = cvd.rolling(w, min_periods=w//2).std()
    df[f'cvd_z_{w}'] = (cvd - mu) / (sigma + 1e-10)

# CVD_DIV: CVD Z-Score 与价格 Z-Score 的背离
for w in [288]:
    px_mu = df['close'].rolling(w, min_periods=w//2).mean()
    px_sigma = df['close'].rolling(w, min_periods=w//2).std()
    px_z = (df['close'] - px_mu) / (px_sigma + 1e-10)
    df[f'cvd_div_{w}'] = df[f'cvd_z_{w}'] - px_z
```

### F2: WHALE_INFLOW — 滚动大单净流入（Rolling 历史分位数定义大单）
```python
# 大单阈值 = 过去 W_whale=2016 根 K 线（7天）的 taker_buy_volume 的 80th percentile
# 注意：expanding 确保训练期无前瞻
taker = df['taker_buy_volume']
seller = df['volume'] - df['taker_buy_volume']
# 用 expanding 后转 rolling 安全版本
thresh_buy = taker.rolling(2016, min_periods=100).quantile(0.80)
thresh_sell = seller.rolling(2016, min_periods=100).quantile(0.80)
big_buy = taker.where(taker > thresh_buy, 0.0)
big_sell = seller.where(seller > thresh_sell, 0.0)
df['whale_inflow_net'] = (big_buy - big_sell).rolling(288, min_periods=50).sum()
# 归一化：除以同窗口总成交额 USD
total_usd = (df['volume'] * df['close']).rolling(288, min_periods=50).sum()
df['whale_inflow_norm'] = df['whale_inflow_net'] / (total_usd / df['close'] + 1e-10)
```

### F3: VOL_SURGE — 量能突增比
```python
vol_ma = df['volume'].rolling(288, min_periods=50).mean()
df['vol_surge'] = df['volume'] / (vol_ma + 1e-10)
```

### F4: PARKINSON_VOL — Parkinson 波动率（微观结构波动率）
```python
import numpy as np
hl_ratio = np.log(df['high'] / df['low']) ** 2
pk_raw = hl_ratio / (4 * np.log(2))
df['parkinson_vol_288'] = pk_raw.rolling(288, min_periods=50).mean() ** 0.5
# ATR
atr_raw = (df['high'] - df['low']).rolling(288, min_periods=50).mean()
df['atr_pct_288'] = atr_raw / (df['close'] + 1e-10)
# 波动率分位数（Regime Filter）
df['atr_pct_rank'] = df['atr_pct_288'].rolling(2016, min_periods=200).rank(pct=True)
# REGIME: 0=低波动休眠, 1=正常, 2=高波动
df['regime'] = pd.cut(df['atr_pct_rank'], bins=[0, 0.15, 0.70, 1.0],
                       labels=[0, 1, 2]).astype(float)
```

### F5: EMA_TREND — 多周期 EMA 趋势门禁
```python
# 5m bar: 12根=1h, 48根=4h
df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
df['ema_48'] = df['close'].ewm(span=48, adjust=False).mean()
df['trend_1h'] = np.sign(df['ema_12'] - df['ema_48'])
# 4h trend gate: 48根=4h, 192根=16h
df['ema_192'] = df['close'].ewm(span=192, adjust=False).mean()
df['trend_4h'] = np.sign(df['ema_48'] - df['ema_192'])
```

### F6: CARRY_FUNDING — 资金费率（当期及方向）
```python
# funding_rate 来自 data_manifest 中标注的字段（2026-09 后真实，之前 NaN）
df['funding_rate_sign'] = np.sign(df['funding_rate'].fillna(0))
df['funding_rate_abs'] = df['funding_rate'].abs()
# Carry 状态: funding > 0.01% 且价格在上升 -> 多头拥挤, 危险; < 0 -> 空头支付, 多头有利
```

### F7: COMBINED_SIGNAL — 组合信号（基线规则版，模型前基准）
```python
# 多头信号: trend_1h>0 AND trend_4h>0 AND cvd_div_288>1.2 AND vol_surge>1.3 AND regime>0
df['signal_long'] = (
    (df['trend_1h'] > 0) & (df['trend_4h'] > 0) &
    (df['cvd_div_288'] > 1.2) & (df['vol_surge'] > 1.3) &
    (df['regime'] > 0)
).astype(int)
df['signal_short'] = (
    (df['trend_1h'] < 0) & (df['trend_4h'] < 0) &
    (df['cvd_div_288'] < -1.2) & (df['vol_surge'] > 1.3) &
    (df['regime'] > 0)
).astype(int)
```

## 因子有效性报告（IC 与分层收益）
对每个因子 F 计算：
- Rank IC = spearmanr(F_t, r_{t+1})，其中 r_{t+1} = (close_{t+1} - close_t) / close_t
- 注意：IC 计算时必须将 F_t 与 r_{t+1} 做严格 shift(1)，避免前瞻
```python
future_ret = df['close'].shift(-1) / df['close'] - 1  # 未来1根bar收益（只用于报告IC，不用于信号）
for fname in factor_names:
    ic = spearmanr(df[fname].dropna(), future_ret.dropna())[0]
```

## 输出规范

### data/gold/features_5m.parquet
包含所有原始列 + 全部因子列，不删除原始数据。
额外添加元数据列：
- `factor_version`: 字符串常量 "v1.0.0"

### data/factor_report.json
```json
{
  "generated_at_utc": "...",
  "input_sha256": "<hash of silver parquet>",
  "output_sha256": "<hash of gold parquet>",
  "factor_count": 15,
  "factors": {
    "cvd_z_288": {"ic_mean": 0.0XX, "ic_std": 0.0XX, "null_pct": X.X},
    "cvd_div_288": {"ic_mean": ..., ...},
    ...
  },
  "regime_distribution": {"0": <pct>, "1": <pct>, "2": <pct>},
  "signal_long_frequency": <pct>,
  "signal_short_frequency": <pct>
}
```

## 完成条件
1. `data/gold/features_5m.parquet` 存在且可读
2. `data/factor_report.json` 存在，factor_count > 0
3. 所有 IC 均为真实数值（非 NaN 全覆盖）
4. 打印 "GATE1_COMPLETE" 到 stdout
5. exit(0)
