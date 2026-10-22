import pyarrow.parquet as pq, pandas as pd, numpy as np, json, hashlib, os
from scipy.stats import spearmanr

df = pq.read_table('data/silver/doge_aligned_5m.parquet').to_pandas()
df['ts_utc'] = pd.to_datetime(df['ts_utc'], utc=True)
df = df.sort_values('ts_ms').reset_index(drop=True)
print(f"Loaded: {len(df):,} rows, {df['ts_utc'].min().date()} to {df['ts_utc'].max().date()}")

# ==== F1: CVD Z-Score ====
delta = df['taker_buy_volume'] - (df['volume'] - df['taker_buy_volume'])
cvd = delta.cumsum()
for w in [288, 1440]:
    mu = cvd.rolling(w, min_periods=w//2).mean()
    sigma = cvd.rolling(w, min_periods=w//2).std()
    df[f'cvd_z_{w}'] = (cvd - mu) / (sigma + 1e-10)

# CVD Divergence (vs price Z-score)
for w in [288]:
    px_mu = df['close'].rolling(w, min_periods=w//2).mean()
    px_sigma = df['close'].rolling(w, min_periods=w//2).std()
    px_z = (df['close'] - px_mu) / (px_sigma + 1e-10)
    df[f'cvd_div_{w}'] = df[f'cvd_z_{w}'] - px_z

# ==== F2: Rolling Whale Inflow ====
taker = df['taker_buy_volume'].fillna(0)
seller = (df['volume'] - df['taker_buy_volume']).clip(lower=0)
thresh_buy = taker.rolling(2016, min_periods=100).quantile(0.80)
thresh_sell = seller.rolling(2016, min_periods=100).quantile(0.80)
big_buy = taker.where(taker > thresh_buy, 0.0)
big_sell = seller.where(seller > thresh_sell, 0.0)
df['whale_inflow_net'] = (big_buy - big_sell).rolling(288, min_periods=50).sum()
total_usd = (df['volume'] * df['close']).rolling(288, min_periods=50).sum()
df['whale_inflow_norm'] = df['whale_inflow_net'] / (total_usd / (df['close'] + 1e-10) + 1e-10)

# ==== F3: Volume Surge ====
vol_ma = df['volume'].rolling(288, min_periods=50).mean()
df['vol_surge'] = df['volume'] / (vol_ma + 1e-10)

# ==== F4: Parkinson Vol & ATR & Regime ====
hl_ratio = np.log((df['high'] / df['low']).clip(lower=1e-10)) ** 2
pk_raw = hl_ratio / (4 * np.log(2))
df['parkinson_vol_288'] = np.sqrt(pk_raw.rolling(288, min_periods=50).mean())
atr_raw = (df['high'] - df['low']).rolling(288, min_periods=50).mean()
df['atr_pct_288'] = atr_raw / (df['close'] + 1e-10)
df['atr_pct_rank'] = df['atr_pct_288'].rolling(2016, min_periods=200).rank(pct=True)
df['regime'] = pd.cut(
    df['atr_pct_rank'].fillna(0.5),
    bins=[-0.01, 0.15, 0.70, 1.01],
    labels=[0, 1, 2]
).astype(float)

# ==== F5: EMA Trend ====
df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
df['ema_48'] = df['close'].ewm(span=48, adjust=False).mean()
df['ema_192'] = df['close'].ewm(span=192, adjust=False).mean()
df['trend_1h'] = np.sign(df['ema_12'] - df['ema_48'])
df['trend_4h'] = np.sign(df['ema_48'] - df['ema_192'])

# ==== F6: Funding Rate Carry ====
df['funding_rate_sign'] = np.sign(df['funding_rate'].fillna(0))
df['funding_rate_abs'] = df['funding_rate'].abs().fillna(0)

# ==== F7: Combined Signal (Rule-based Baseline) ====
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

df['factor_version'] = 'v1.0.0'

# ==== IC calculation (report only; shift(-1) for forward return) ====
future_ret = (df['close'].shift(-1) / df['close'] - 1)
factor_names = ['cvd_z_288', 'cvd_z_1440', 'cvd_div_288', 'whale_inflow_norm',
                'vol_surge', 'parkinson_vol_288', 'atr_pct_288',
                'trend_1h', 'trend_4h', 'regime',
                'funding_rate_sign', 'funding_rate_abs',
                'whale_inflow_net', 'atr_pct_rank', 'signal_long']

factor_ic = {}
for fname in factor_names:
    if fname in df.columns:
        mask = df[fname].notna() & future_ret.notna()
        if mask.sum() > 100:
            ic_val = spearmanr(df[fname][mask], future_ret[mask])[0]
            null_pct = df[fname].isna().mean() * 100
            factor_ic[fname] = {'ic_mean': round(float(ic_val), 6), 'null_pct': round(null_pct, 2)}
        else:
            factor_ic[fname] = {'ic_mean': None, 'null_pct': 100.0}

# ==== Output ====
os.makedirs('data/gold', exist_ok=True)
out_path = 'data/gold/features_5m.parquet'
df.to_parquet(out_path, index=False, compression='zstd')
print(f"Written: {out_path} ({os.path.getsize(out_path)/1024/1024:.1f} MB)")

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''): h.update(chunk)
    return h.hexdigest()

factor_report = {
    'generated_at_utc': pd.Timestamp.now(tz='UTC').isoformat(),
    'input_sha256': sha256_file('data/silver/doge_aligned_5m.parquet'),
    'output_sha256': sha256_file(out_path),
    'factor_count': len(factor_ic),
    'factors': factor_ic,
    'regime_distribution': {
        str(int(k)): round(float(v), 4)
        for k, v in df['regime'].value_counts(normalize=True).sort_index().to_dict().items()
    },
    'signal_long_frequency': round(float(df['signal_long'].mean()), 6),
    'signal_short_frequency': round(float(df['signal_short'].mean()), 6)
}
with open('data/factor_report.json', 'w') as f:
    json.dump(factor_report, f, indent=2, ensure_ascii=False)

print(f"Written: data/factor_report.json ({len(factor_ic)} factors)")
print(f"signal_long freq: {factor_report['signal_long_frequency']:.4%}")
print(f"signal_short freq: {factor_report['signal_short_frequency']:.4%}")
print(f"regime dist: {factor_report['regime_distribution']}")
print(f"IC summary:")
for k, v in factor_ic.items():
    print(f"  {k}: ic={v['ic_mean']}, null={v['null_pct']}%")
print(f"GATE1_COMPLETE: gold parquet {len(df):,} rows, {len(df.columns)} columns")
