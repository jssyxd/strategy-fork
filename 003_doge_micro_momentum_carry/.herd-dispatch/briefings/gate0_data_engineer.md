# Gate 0 DataEngineer Agent Briefing
# Role: DataEngineer — 完成即停，不扩展范围

## 任务目标
从 SMB 挂载的数据库中提取、融合、治理 DOGE 历史 5m K 线数据，产出满足五大数学不变量的
`data/silver/doge_aligned_5m.parquet`（目标覆盖 2021-01 至 2026-10）与 `data/data_manifest.json`。

## 约束
- 纯函数确定性管道：每次输入相同必须输出相同，无随机性，无副作用
- 严禁前瞻偏差：resample 左闭右开（每根 5m bar 仅含 [t, t+5min) 内的 1m bars）
- 严禁插值伪造：真实缺口只记录 defect，不合成数据
- 完成即停：写完文件后退出，不执行因子计算

## 数据源（已验证可读）

### Source A: Nautilus 1m OHLCV (5 年 OHLCV，无 taker)
路径前缀: `/mnt/iflow/database/03_governed_lake/nautilus_databank/catalog/data/bar/DOGEUSD.CRYPTO-1-MINUTE-LAST-EXTERNAL/`
文件: 2021.parquet (282,542行), 2022.parquet (522,649行), 2023.parquet (518,141行),
      2024.parquet (524,758行), 2025.parquet (523,954行)
列: timestamp(datetime64 UTC), symbol, timeframe, bar_type, ts_event(ns), ts_init(ns),
    open, high, low, close, volume
时间跨度: 2021-01-01 → 2025-12-31

### Source B: Governed 1h Futures (4.8年，含 taker_buy_volume)
路径: `/mnt/iflow/database/03_governed_lake/v2_parquet_lake/crypto/futures_um/DOGEUSDT/1h/DOGEUSDT_1h_consolidated.parquet`
列: timestamp(ms epoch), datetime(UTC), open, high, low, close, volume, quote_volume, taker_buy_volume
时间跨度: 2022-01-01 → 2026-10-17  (42,009 rows)

### Source C: Governed 5m Futures (6个月，含 taker_buy_volume)
路径: `/mnt/iflow/database/03_governed_lake/v2_parquet_lake/crypto/futures_um/DOGEUSDT/5m/DOGEUSDT_5m_consolidated.parquet`
列: timestamp(ms epoch), datetime(UTC), open, high, low, close, volume, quote_volume, taker_buy_volume
时间跨度: 2026-04-25 → 2026-10-15  (50,000 rows)

### Source D: Project 28d aligned 5m (含 fundingRate)
路径: `data/doge_real_binance_aligned_5m.parquet`
列: open_time(ms), open_dt, open, high, low, close, volume, taker_buy_base, spot_close, fundingTime, fundingRate
时间跨度: 2026-09-17 → 2026-10-15  (8,000 rows)

## 融合算法（确定性步骤）

### 步骤1：读取并标准化 Nautilus 1m → canonical 格式
```python
# ts_event 是纳秒级整数，转换为 UTC datetime
df['ts_utc'] = pd.to_datetime(df['ts_event'], unit='ns', utc=True)
# 统一列名: ts_utc, open, high, low, close, volume
```

### 步骤2：确定性 1m → 5m 重采样（左闭右开）
```python
# resample 规则：label='left', closed='left'
# open = first(open), high = max(high), low = min(low)
# close = last(close), volume = sum(volume)
# 5m bar 的时间戳 = 该 5min 窗口的左端点（开盘时刻）
rule = '5min'
agg = {
    'open': 'first', 'high': 'max', 'low': 'min',
    'close': 'last', 'volume': 'sum'
}
df_5m = df_1m.set_index('ts_utc').resample(rule, label='left', closed='left').agg(agg).dropna(subset=['close'])
```

### 步骤3：计算 1h taker_buy 比例，向下传播至 5m
taker_buy_ratio_1h = taker_buy_volume_1h / volume_1h
用 merge_asof(direction='backward') 将 1h 的 taker_buy_ratio 对齐到每根 5m bar
taker_buy_volume_5m = volume_5m * taker_buy_ratio_1h (前向填充，方向 backward)
用 Source C (5m真实 taker_buy) 覆盖 2026-04-25 之后的数据（直接使用原始值，不用代理）

### 步骤4：Funding Rate 填充
从 Source D (28d) 取 fundingRate，用 merge_asof(backward) 对齐
缺失期(2021-2026-09)统一填 NaN，不伪造

### 步骤5：五大数学不变量审计
```python
# 不变量1: 时间戳严格单调递增
assert (df['ts_ms'].diff().dropna() > 0).all(), "FAIL: 时间戳非单调递增"
# 不变量2: 去重
assert df['ts_ms'].duplicated().sum() == 0, "FAIL: 存在重复时间戳"
# 不变量3: OHLC 几何包络
assert (df['high'] >= df[['open','close']].max(axis=1)).all()
assert (df['low'] <= df[['open','close']].min(axis=1)).all()
# 不变量4: 价格正值
assert (df[['open','high','low','close']] > 0).all().all()
# 不变量5: 量能非负
assert (df['volume'] >= 0).all()
```

违反任何不变量的行→记录到 defect log，从主表删除，不伪造插值。

### 步骤6：输出
输出 `data/silver/doge_aligned_5m.parquet`，列定义：
- ts_ms: int64, UTC 毫秒时间戳（主键）
- ts_utc: datetime64[ns, UTC]
- open, high, low, close: float64
- volume: float64（基础货币 DOGE）
- taker_buy_volume: float64（Nautilus 年段用 1h 代理比例，2026-04 后用 5m 真实值）
- taker_buy_is_proxy: bool (True=代理值, False=真实5m直接观测)
- funding_rate: float64 (2026-09 之前为 NaN)

输出 `data/data_manifest.json`：
```json
{
  "generated_at_utc": "<ISO8601>",
  "sources": [...],
  "shape": [rows, cols],
  "ts_range": {"start": "...", "end": "..."},
  "defects_count": <int>,
  "five_invariants_passed": true,
  "sha256": "<hash of parquet file>"
}
```

## 完成条件
1. `data/silver/doge_aligned_5m.parquet` 存在且可读
2. `data/data_manifest.json` 存在，five_invariants_passed=true
3. 打印 "GATE0_COMPLETE" 到 stdout
4. exit(0)
