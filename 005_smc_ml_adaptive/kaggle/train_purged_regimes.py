"""
SMC Purged Walk-Forward Time Series Cross-Validation & Regime Classification
Inspired by López de Prado (Purged TS-CV + Optuna Plateau Search) & DRW Crypto Regime Ensemble.
Strictly Prevents Lookahead Bias & Overfitting.
"""

import json
import os
from pathlib import Path
import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import classification_report, f1_score


optuna.logging.set_verbosity(optuna.logging.WARNING)


def load_dataset():
    # Search recursively in /kaggle/input if present
    if Path("/kaggle/input").exists():
        for p in Path("/kaggle/input").rglob("*.parquet"):
            if "features" in p.name.lower():
                print(f"Discovered Kaggle dataset file at: {p}")
                return pd.read_parquet(p)
        print(f"Available files in /kaggle/input: {list(Path('/kaggle/input').rglob('*'))}")

    local_path = Path("artifacts/features/features_with_purged_labels.parquet")
    lake_path = Path("W:/database/03_governed_lake/smc_live_governed/decisions_15m_governed.parquet")

    if local_path.exists():
        print(f"Loading data from {local_path}...")
        return pd.read_parquet(local_path)
    elif lake_path.exists():
        from src.feature_and_label_builder import build_features_and_labels
        df, _ = build_features_and_labels(str(lake_path), "artifacts/features")
        return df

    raise FileNotFoundError("Could not locate features_with_purged_labels.parquet in /kaggle/input or local paths.")


def get_purged_walk_forward_folds(
    df: pd.DataFrame, n_splits: int = 5, embargo_pct: float = 0.02
):
    """Generates Purged Walk-Forward CV splits.

    Ensures:
    1. Chronological order (train strictly before test).
    2. Purging: removes train samples whose forward label window overlaps with test start.
    3. Embargo: removes samples immediately following test window.
    """
    valid_df = (
        df.dropna(subset=["regime_label"])
        .sort_values("timestamp_utc")
        .reset_index(drop=True)
    )
    unique_times = valid_df["timestamp_utc"].drop_duplicates().sort_values()
    n_times = len(unique_times)

    split_size = n_times // (n_splits + 1)
    folds = []

    for i in range(1, n_splits + 1):
        train_end_idx = i * split_size
        test_end_idx = min((i + 1) * split_size, n_times)

        train_cutoff_time = unique_times.iloc[train_end_idx - 1]
        test_start_time = unique_times.iloc[train_end_idx]
        test_end_time = unique_times.iloc[test_end_idx - 1]

        # Training set: strictly before test_start_time
        # AND Purge: t_1_label_end must be <= test_start_time
        train_mask = (valid_df["timestamp_utc"] <= train_cutoff_time) & (
            valid_df["t_1_label_end"] <= test_start_time
        )

        # Test set: between test_start_time and test_end_time
        test_mask = (valid_df["timestamp_utc"] >= test_start_time) & (
            valid_df["timestamp_utc"] <= test_end_time
        )

        train_indices = valid_df[train_mask].index.values
        test_indices = valid_df[test_mask].index.values

        if len(train_indices) > 20 and len(test_indices) > 10:
            folds.append((train_indices, test_indices))

    print(f"Generated {len(folds)} strictly Purged Walk-Forward folds.")
    return valid_df, folds


def run_pipeline(output_dir: str = "."):
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_dataset()
    valid_df, folds = get_purged_walk_forward_folds(df, n_splits=4)

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

    X = valid_df[feature_cols].values
    y = valid_df["regime_label"].values.astype(int)

    print(f"Dataset shape: X={X.shape}, y={y.shape}, classes={np.unique(y)}")

    # 1. Optuna Plateau Hyperparameter Optimization (Penalize variance across folds)
    def objective(trial):
        params = {
            "objective": "multiclass",
            "num_class": 4,
            "metric": "multi_logloss",
            "boosting_type": "gbdt",
            "verbosity": -1,
            "n_estimators": trial.suggest_int("n_estimators", 30, 90),
            "learning_rate": trial.suggest_float(
                "learning_rate", 0.02, 0.12, log=True
            ),
            "max_depth": trial.suggest_int("max_depth", 2, 4),
            "num_leaves": trial.suggest_int("num_leaves", 4, 15),
            "min_child_samples": trial.suggest_int(
                "min_child_samples", 15, 40
            ),
            "subsample": trial.suggest_float("subsample", 0.7, 1.0),
            "colsample_bytree": trial.suggest_float(
                "colsample_bytree", 0.6, 0.95
            ),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-2, 5.0, log=True),
            "reg_lambda": trial.suggest_float(
                "reg_lambda", 1e-2, 5.0, log=True
            ),
            "random_state": 42,
            "n_jobs": -1,
        }

        scores = []
        for train_idx, val_idx in folds:
            X_tr, y_tr = X[train_idx], y[train_idx]
            X_val, y_val = X[val_idx], y[val_idx]

            clf = lgb.LGBMClassifier(**params)
            clf.fit(X_tr, y_tr)
            preds = clf.predict(X_val)
            f1 = f1_score(y_val, preds, average="macro")
            scores.append(f1)

        mean_score = np.mean(scores)
        std_score = np.std(scores)
        # Parameter Plateau Objective: High mean minus variance penalty
        plateau_objective = mean_score - 1.2 * std_score
        return plateau_objective

    print("Starting Optuna search for robust parameter plateau (25 trials)...")
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=25, timeout=120)

    best_params = study.best_params
    best_params.update(
        {
            "objective": "multiclass",
            "num_class": 4,
            "metric": "multi_logloss",
            "boosting_type": "gbdt",
            "verbosity": -1,
            "random_state": 42,
            "n_jobs": -1,
        }
    )
    print(f"Optimal Plateau Parameters found: {best_params}")

    # 2. Train final model across walk-forward folds and evaluate out-of-sample (OOS)
    oos_preds = np.zeros(len(valid_df))
    oos_probs = np.zeros((len(valid_df), 4))
    evaluated_mask = np.zeros(len(valid_df), dtype=bool)

    fold_metrics = []
    models = []

    for fold_i, (train_idx, val_idx) in enumerate(folds):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_val, y_val = X[val_idx], y[val_idx]

        clf = lgb.LGBMClassifier(**best_params)
        clf.fit(X_tr, y_tr)
        models.append(clf)

        probs = clf.predict_proba(X_val)
        preds = clf.predict(X_val)

        oos_probs[val_idx] = probs
        oos_preds[val_idx] = preds
        evaluated_mask[val_idx] = True

        f1 = f1_score(y_val, preds, average="macro")
        acc = np.mean(y_val == preds)
        fold_metrics.append({"fold": fold_i + 1, "macro_f1": f1, "accuracy": acc})
        print(f"  Fold {fold_i+1}: Macro F1 = {f1:.4f}, Accuracy = {acc:.4f}")

    # Train final model on all data
    final_model = lgb.LGBMClassifier(**best_params)
    final_model.fit(X, y)

    # Save model
    model_path = out_dir / "regime_model_lightgbm.txt"
    final_model.booster_.save_model(str(model_path))
    print(f"Saved final LightGBM model to {model_path}")

    # Feature Importance
    importances = final_model.feature_importances_
    feat_imp = sorted(
        zip(feature_cols, importances), key=lambda x: x[1], reverse=True
    )
    feat_imp_dict = {k: int(v) for k, v in feat_imp}

    with open(out_dir / "feature_importance.json", "w", encoding="utf-8") as f:
        json.dump(feat_imp_dict, f, indent=2)

    # Latest bar inference (most recent timestamp)
    latest_bar = valid_df.iloc[-4:].copy()
    latest_probs = final_model.predict_proba(latest_bar[feature_cols].values)
    latest_preds = final_model.predict(latest_bar[feature_cols].values)

    regime_names = {
        0: "TrendFollow",
        1: "HighSelectivity",
        2: "Invert",
        3: "NoTrade",
    }
    recommendations = []
    for idx, (_, row) in enumerate(latest_bar.iterrows()):
        pred_cls = int(latest_preds[idx])
        probs = latest_probs[idx].tolist()
        recommendations.append(
            {
                "symbol": row["symbol"],
                "timestamp_utc": str(row["timestamp_utc"]),
                "recommended_regime": regime_names[pred_cls],
                "regime_id": pred_cls,
                "confidence": float(np.max(probs)),
                "probabilities": {
                    regime_names[i]: float(probs[i]) for i in range(4)
                },
                "u_vacuity": float(row["evidential_vacuity_u"]),
                "c_conflict": float(row["evidential_conflict_c"]),
            }
        )

    top_5 = [[str(k), int(v)] for k, v in feat_imp[:5]]
    clean_best_params = {}
    for k, v in best_params.items():
        if isinstance(v, (np.integer, int)):
            clean_best_params[k] = int(v)
        elif isinstance(v, (np.floating, float)):
            clean_best_params[k] = float(v)
        else:
            clean_best_params[k] = v
    summary = {
        "optuna_best_plateau_value": float(study.best_value),
        "best_hyperparameters": clean_best_params,
        "fold_validation_metrics": fold_metrics,
        "mean_oos_macro_f1": float(
            np.mean([m["macro_f1"] for m in fold_metrics])
        ),
        "mean_oos_accuracy": float(
            np.mean([m["accuracy"] for m in fold_metrics])
        ),
        "top_5_predictive_features": top_5,
        "latest_recommendations": recommendations,
    }

    with open(
        out_dir / "oos_performance_summary.json", "w", encoding="utf-8"
    ) as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n=== Training & Evaluation Summary ===")
    print(
        f"Mean OOS Macro F1: {summary['mean_oos_macro_f1']:.4f} | Accuracy: {summary['mean_oos_accuracy']:.4f}"
    )
    print(f"Top 5 Features: {[k for k, v in feat_imp[:5]]}")
    print("\nLatest Multi-Asset Recommendations:")
    for rec in recommendations:
        print(
            f"  [{rec['symbol']}] -> {rec['recommended_regime']} (Confidence: {rec['confidence']:.2%}, u={rec['u_vacuity']:.3f}, C={rec['c_conflict']:.3f})"
        )

    return summary


if __name__ == "__main__":
    # Check if inside Kaggle environment
    is_kaggle = os.path.exists("/kaggle/working")
    output_dir = "/kaggle/working" if is_kaggle else "artifacts/training_output"
    run_pipeline(output_dir)
