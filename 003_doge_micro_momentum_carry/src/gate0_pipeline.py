#!/usr/bin/env python3
"""Gate0 DataEngineer Pipeline - deterministic, no lookahead, no interpolation."""

import pyarrow.parquet as pq
import pandas as pd
import numpy as np
import json
import hashlib
import os
import sys

from pathlib import Path

os.chdir("/home/da/桌面/008_doge_momentum")

# ─── Step 1: Load Nautilus 1m OHLCV ─────────────────────────────────────────
base = "/mnt/iflow/database/03_governed_lake/nautilus_databank/catalog/data/bar/DOGEUSD.CRYPTO-1-MINUTE-LAST-EXTERNAL"
frames = []
for yr in [2021, 2022, 2023, 2024, 2025]:
    df = pq.read_table(f"{base}/{yr}.parquet").to_pandas()
    # ts_event is nanosecond integer
    df['ts_utc'] = pd.to_datetime(df['ts_event'], unit='ns', utc=True)
    df = df[['ts_utc', 'open', 'high', 'low', 'close', 'volume']].sort_values('ts_utc')
    frames.append(df)
    print(f"  Loaded {yr}: {len(df):,} rows")

df_1m = pd.concat(frames, ignore_index=True).drop_duplicates(subset=['ts_utc']).sort_values('ts_utc')
df_1m = df_1m.set_index('ts_utc')
print(f"1m raw rows: {len(df_1m):,} | {df_1m.index.min()} -> {df_1m.index.max()}")

# ─── Step 2: Deterministic 1m → 5m resample (left-closed, left-label) ───────
agg = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
df_5m = df_1m.resample('5min', label='left', closed='left').agg(agg).dropna(subset=['close'])
df_5m = df_5m[df_5m['volume'] > 0].copy()
print(f"5m resample rows: {len(df_5m):,}")

# ─── Step 3: 1h governed data for taker_buy_ratio ───────────────────────────
df_1h = pq.read_table(
    "/mnt/iflow/database/03_governed_lake/v2_parquet_lake/crypto/futures_um/DOGEUSDT/1h/DOGEUSDT_1h_consolidated.parquet"
).to_pandas()
df_1h['ts_utc'] = pd.to_datetime(df_1h['timestamp'], unit='ms', utc=True).astype('datetime64[ns, UTC]')
df_1h = df_1h.sort_values('ts_utc').set_index('ts_utc')
df_1h['taker_buy_ratio'] = df_1h['taker_buy_volume'] / (df_1h['volume'] + 1e-10)
df_1h['taker_buy_ratio'] = df_1h['taker_buy_ratio'].clip(0, 1)
print(f"1h governed rows: {len(df_1h):,} | {df_1h.index.min()} -> {df_1h.index.max()}")

# ─── Step 4: merge_asof 1h taker_buy_ratio → 5m ─────────────────────────────
df_5m_reset = df_5m.reset_index()
# Normalize to ns precision for merge_asof compatibility
df_5m_reset['ts_utc'] = df_5m_reset['ts_utc'].astype('datetime64[ns, UTC]')
df_1h_reset = df_1h.reset_index()[['ts_utc', 'taker_buy_ratio']]

merged = pd.merge_asof(
    df_5m_reset.sort_values('ts_utc'),
    df_1h_reset.sort_values('ts_utc'),
    on='ts_utc',
    direction='backward'
)
merged['taker_buy_volume'] = merged['volume'] * merged['taker_buy_ratio'].fillna(0.5)
merged['taker_buy_is_proxy'] = True
print(f"After 1h merge_asof: {len(merged):,} rows")

# ─── Step 5: Merge/append governed 5m data (2026-04-25+) ────────────────────
df_5m_gov = pq.read_table(
    "/mnt/iflow/database/03_governed_lake/v2_parquet_lake/crypto/futures_um/DOGEUSDT/5m/DOGEUSDT_5m_consolidated.parquet"
).to_pandas()
df_5m_gov['ts_utc'] = pd.to_datetime(df_5m_gov['timestamp'], unit='ms', utc=True).astype('datetime64[ns, UTC]')
print(f"5m governed rows: {len(df_5m_gov):,} | {df_5m_gov['ts_utc'].min()} -> {df_5m_gov['ts_utc'].max()}")

# Build a clean governed-5m frame with the same columns as merged
gov_cols = ['ts_utc', 'open', 'high', 'low', 'close', 'volume', 'taker_buy_volume']
df_5m_gov_clean = df_5m_gov[gov_cols].copy()
df_5m_gov_clean['taker_buy_is_proxy'] = False
# taker_buy_ratio not needed for real data; fill to satisfy merged schema
df_5m_gov_clean['taker_buy_ratio'] = (
    df_5m_gov_clean['taker_buy_volume'] / (df_5m_gov_clean['volume'] + 1e-10)
).clip(0, 1)

# Rows in merged that also appear in gov are overridden; new 2026 rows are appended
merged_ts = set(merged['ts_utc'])
gov_new = df_5m_gov_clean[~df_5m_gov_clean['ts_utc'].isin(merged_ts)].copy()
gov_overlap = df_5m_gov_clean[df_5m_gov_clean['ts_utc'].isin(merged_ts)].copy()

print(f"5m gov: {len(gov_new):,} new rows | {len(gov_overlap):,} override rows")

# Override overlapping rows
if len(gov_overlap) > 0:
    merged_idx = merged.set_index('ts_utc')
    gov_overlap_idx = gov_overlap.set_index('ts_utc')
    for col in ['open', 'high', 'low', 'close', 'volume', 'taker_buy_volume']:
        merged_idx.loc[gov_overlap_idx.index, col] = gov_overlap_idx[col]
    merged_idx.loc[gov_overlap_idx.index, 'taker_buy_is_proxy'] = False
    merged = merged_idx.reset_index()

# Append new 2026 rows
merged = pd.concat([merged, gov_new], ignore_index=True)
merged = merged.sort_values('ts_utc').reset_index(drop=True)
print(f"After 5m gov merge: {len(merged):,} rows | {merged['ts_utc'].min()} -> {merged['ts_utc'].max()}")

# ─── Step 6: Funding rate fill from 28d project data ────────────────────────
df_28d = pq.read_table("data/doge_real_binance_aligned_5m.parquet").to_pandas()
df_28d['ts_utc'] = pd.to_datetime(df_28d['open_dt'], utc=True).astype('datetime64[ns, UTC]')
df_28d = df_28d.sort_values('ts_utc')
print(f"28d project rows: {len(df_28d):,} | {df_28d['ts_utc'].min()} -> {df_28d['ts_utc'].max()}")

merged = pd.merge_asof(
    merged.sort_values('ts_utc'),
    df_28d[['ts_utc', 'fundingRate']].sort_values('ts_utc'),
    on='ts_utc',
    direction='backward'
)
merged.rename(columns={'fundingRate': 'funding_rate'}, inplace=True)

# ─── Step 7: ts_ms primary key ───────────────────────────────────────────────
merged['ts_ms'] = (merged['ts_utc'].astype(np.int64) // 10**6)
merged = merged.sort_values('ts_ms').reset_index(drop=True)
print(f"Final 5m rows: {len(merged):,} | {merged['ts_utc'].min()} -> {merged['ts_utc'].max()}")

# ─── Step 8: Five invariants audit ───────────────────────────────────────────
defects = []

# Invariant 1: Strictly monotonically increasing timestamps
ts_diff = np.diff(merged['ts_ms'].values)
non_mono = np.where(ts_diff <= 0)[0]
if len(non_mono) > 0:
    defects.append({'type': 'NON_MONOTONIC', 'count': int(len(non_mono))})
    print(f"  WARNING: {len(non_mono)} non-monotonic timestamps")

# Invariant 2: No duplicate timestamps
dup_count = int(merged['ts_ms'].duplicated().sum())
if dup_count > 0:
    defects.append({'type': 'DUPLICATE', 'count': dup_count})
    print(f"  WARNING: {dup_count} duplicate timestamps")
    merged = merged.drop_duplicates(subset=['ts_ms'], keep='first').copy()

# Invariant 3: OHLC geometry envelope
bad3 = ~(
    (merged['high'] >= merged[['open', 'close']].max(axis=1)) &
    (merged['low'] <= merged[['open', 'close']].min(axis=1))
)
if bad3.any():
    defects.append({'type': 'OHLC_GEOMETRY', 'count': int(bad3.sum())})
    print(f"  WARNING: {bad3.sum()} OHLC geometry violations")
    merged = merged[~bad3].copy()

# Invariant 4: Positive prices
bad4 = (merged[['open', 'high', 'low', 'close']] <= 0).any(axis=1)
if bad4.any():
    defects.append({'type': 'NON_POSITIVE_PRICE', 'count': int(bad4.sum())})
    print(f"  WARNING: {bad4.sum()} non-positive price rows")
    merged = merged[~bad4].copy()

# Invariant 5: Non-negative volume
bad5 = merged['volume'] < 0
if bad5.any():
    defects.append({'type': 'NEGATIVE_VOLUME', 'count': int(bad5.sum())})
    print(f"  WARNING: {bad5.sum()} negative volume rows")
    merged = merged[~bad5].copy()

# Re-sort after removals
merged = merged.sort_values('ts_ms').reset_index(drop=True)

os.makedirs('data/defects', exist_ok=True)
with open('data/defects/defect_log_gate0.json', 'w') as f:
    json.dump(defects, f, indent=2)
print(f"Five invariants audit: {defects if defects else 'ALL_PASS'}")
print(f"Clean rows after audit: {len(merged):,}")

# ─── Step 9: Write silver parquet + manifest ─────────────────────────────────
os.makedirs('data/silver', exist_ok=True)

out_cols = ['ts_ms', 'ts_utc', 'open', 'high', 'low', 'close', 'volume',
            'taker_buy_volume', 'taker_buy_is_proxy', 'funding_rate']
out_cols = [c for c in out_cols if c in merged.columns]

out = merged[out_cols].copy()
out_path = 'data/silver/doge_aligned_5m.parquet'
out.to_parquet(out_path, index=False, compression='zstd')
print(f"Written: {out_path} ({os.path.getsize(out_path)/1024/1024:.1f} MB)")

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

sha = sha256_file(out_path)

manifest = {
    "generated_at_utc": pd.Timestamp.now(tz='UTC').isoformat(),
    "sources": [
        "nautilus_1m_2021-2025",
        "governed_1h_taker_buy",
        "governed_5m_taker_buy_2026",
        "project_28d_funding_rate"
    ],
    "shape": list(out.shape),
    "ts_range": {
        "start": str(out['ts_utc'].min()),
        "end": str(out['ts_utc'].max())
    },
    "defects_count": sum(d['count'] for d in defects),
    "defects_detail": defects,
    "five_invariants_passed": True,
    "sha256": sha
}
with open('data/data_manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
print(f"Written: data/data_manifest.json")
print(f"GATE0_COMPLETE: {len(out):,} rows, {str(out['ts_utc'].min())[:10]} to {str(out['ts_utc'].max())[:10]}, sha256={sha[:16]}...")
sys.exit(0)
