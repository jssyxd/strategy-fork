"""
Feature and Label Engineering with Strict Anti-Lookahead Purge & Embargo Metadata.
Incorporates:
- SMC features (EMA pullbacks, ATR ratio, Volume Spike, CLV, Evidential u/C)
- Microsoft Qlib Alpha158-inspired operators (Normalized momentum, rolling volatility, dispersion)
- Purged Cross-Validation metadata (t_0, t_1 label realization, t_embargo)
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd


def build_features_and_labels(input_parquet: str, output_dir: str):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(input_parquet)
    df = df.sort_values(["symbol", "timestamp_utc"]).reset_index(drop=True)

    # 1. Causal Price & Trend Features (All operations causal, <= t)
    df["close_to_ema20"] = (df["close"] - df["ema20"]) / (df["atr14"] + 1e-9)
    df["close_to_ema50"] = (df["close"] - df["ema50"]) / (df["atr14"] + 1e-9)
    df["ema20_to_ema50"] = (df["ema20"] - df["ema50"]) / (df["atr14"] + 1e-9)

    # Momentum / Returns (Qlib style)
    for k in [1, 2, 4, 8, 16]:
        df[f"ret_{k}"] = df.groupby("symbol")["close"].pct_change(k)

    # Rolling Volatility
    for win in [8, 16, 32]:
        df[f"vol_std_{win}"] = df.groupby("symbol")["ret_1"].transform(
            lambda x: x.rolling(win, min_periods=4).std()
        )

    # Volume & Pressure Features
    df["vol_ratio_log"] = np.log(df["volume_ratio"].clip(lower=0.01))
    df["clv_abs"] = df["clv"].abs()

    # SMC Evidence & Direction Features
    df["score_diff"] = df["score_long"] - df["score_short"]
    df["score_max"] = np.maximum(df["score_long"], df["score_short"])
    df["signal_dir"] = np.where(
        df["score_long"] > df["score_short"],
        1,
        np.where(df["score_short"] > df["score_long"], -1, 0),
    )

    # Evidential Vacuity & Conflict
    df["evidential_vacuity_u"] = df["u"]
    df["evidential_conflict_c"] = df["C"]
    df["evidential_composite"] = df["u"] * 0.6 + df["C"] * 0.4

    # 2. Cross-Asset Market Regime Features (Macro alignment at timestamp t)
    cross_ret = (
        df.groupby("timestamp_utc")["ret_4"]
        .agg(["mean", "std"])
        .rename(
            columns={"mean": "mkt_ret_4_mean", "std": "mkt_ret_4_dispersion"}
        )
    )
    cross_u = (
        df.groupby("timestamp_utc")["u"].mean().rename("mkt_evidential_u_mean")
    )
    cross_c = (
        df.groupby("timestamp_utc")["C"].mean().rename("mkt_evidential_c_mean")
    )

    df = df.merge(cross_ret, on="timestamp_utc", how="left")
    df = df.merge(cross_u, on="timestamp_utc", how="left")
    df = df.merge(cross_c, on="timestamp_utc", how="left")

    # 3. Strictly Forward Target & Purged Labeling (Horizon H = 8 bars = 2 hrs)
    H = 8
    df["fwd_close_8"] = df.groupby("symbol")["close"].shift(-H)
    df["fwd_ret_atr"] = (df["fwd_close_8"] - df["close"]) / (
        df["atr14"] + 1e-9
    )
    df["strat_fwd_r"] = df["signal_dir"] * df["fwd_ret_atr"]

    # Discrete Regime Definition:
    # 0: TrendFollow
    # 1: HighSelectivity
    # 2: Invert (MeanRevert / Fakeout)
    # 3: NoTrade (Cash)
    def assign_regime(row):
        if pd.isna(row["strat_fwd_r"]):
            return np.nan
        r = row["strat_fwd_r"]
        u = row["u"]
        c = row["C"]

        if u > 0.42 or c > 0.50:
            return 3  # NoTrade: high conflict or high vacuity
        if r >= 1.0 and u <= 0.35 and c < 0.40:
            return 0  # TrendFollow: clean trend, low uncertainty
        elif 0.2 <= r < 1.0:
            return 1  # HighSelectivity: modest positive expectancy
        elif r <= -0.8 and abs(row["fwd_ret_atr"]) >= 0.8:
            return 2  # Invert: clear negative correlation, inverse yields positive
        else:
            return 3  # NoTrade: chop, whipsaw, or ambiguous

    df["regime_label"] = df.apply(assign_regime, axis=1)

    # 4. Purge & Embargo Metadata (Lopez de Prado specification)
    df["t_0_decision"] = df["timestamp_utc"]
    df["t_1_label_end"] = df["timestamp_utc"] + pd.Timedelta(minutes=15 * H)
    # Embargo buffer = 8 bars after label end
    df["t_embargo_end"] = df["t_1_label_end"] + pd.Timedelta(minutes=15 * 8)

    # Save governed features and metadata
    feat_parquet = out_path / "features_with_purged_labels.parquet"
    df.to_parquet(feat_parquet, compression="zstd")
    print(f"Features saved to {feat_parquet} ({len(df)} rows)")

    feature_cols = [
        "close_to_ema20",
        "close_to_ema50",
        "ema20_to_ema50",
        "ret_1",
        "ret_2",
        "ret_4",
        "ret_8",
        "ret_16",
        "vol_std_8",
        "vol_std_16",
        "vol_std_32",
        "atr_ratio",
        "vol_ratio_log",
        "clv",
        "clv_abs",
        "score_diff",
        "score_max",
        "signal_dir",
        "evidential_vacuity_u",
        "evidential_conflict_c",
        "evidential_composite",
        "mkt_ret_4_mean",
        "mkt_ret_4_dispersion",
        "mkt_evidential_u_mean",
        "mkt_evidential_c_mean",
    ]

    meta = {
        "dataset_shape": list(df.shape),
        "feature_count": len(feature_cols),
        "feature_columns": feature_cols,
        "label_column": "regime_label",
        "label_mapping": {
            0: "TrendFollow",
            1: "HighSelectivity",
            2: "Invert",
            3: "NoTrade",
        },
        "purge_embargo_spec": {
            "forward_horizon_bars": H,
            "forward_horizon_minutes": H * 15,
            "embargo_bars": 8,
            "embargo_minutes": 120,
            "strict_anti_lookahead": True,
        },
        "label_distribution": df["regime_label"]
        .value_counts(dropna=False)
        .to_dict(),
    }

    with open(out_path / "feature_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(
        f"Feature metadata saved to {out_path / 'feature_metadata.json'}"
    )
    return df, feature_cols


if __name__ == "__main__":
    build_features_and_labels(
        "W:/database/03_governed_lake/smc_live_governed/decisions_15m_governed.parquet",
        "artifacts/features",
    )
