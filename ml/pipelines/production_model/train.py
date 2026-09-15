"""Production Prediction model training — Phase 15.

Time-aware split (train on earlier 80% of days, test on the most recent
20% — never random), three regressors compared, best saved as artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from xgboost import XGBRegressor

REPO_ROOT = Path(__file__).resolve().parents[3]
FEATURES_PATH = REPO_ROOT / "ml" / "data" / "processed" / "production_features.parquet"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "production_prediction_model.joblib"
META_PATH = ARTIFACTS_DIR / "model_metadata.json"

RANDOM_STATE = 42
TEST_FRACTION = 0.2  # most recent 20% of days held out

FEATURE_COLUMNS = [
    "planned_production",
    "ore_grade",
    "rainfall_1d",
    "rainfall_7d",
    "rainfall_30d",
    "fleet_availability",
    "fleet_downtime",
    "fleet_maintenance",
    "fleet_capacity",
    "active_units",
    "blast_delay_same_day",
    "blast_delay_last_3d",
]

TARGET = "actual_production"


def time_aware_split(frame: pd.DataFrame):
    """Temporal split: earlier 80% train, most recent 20% test."""
    dates = np.sort(frame["date"].unique())
    cutoff = dates[int(len(dates) * (1 - TEST_FRACTION))]
    train = frame[frame["date"] < cutoff]
    test = frame[frame["date"] >= cutoff]
    return train, test, pd.Timestamp(cutoff)


def prepare(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Feature matrix + target with missingness flags folded in."""
    X = frame.copy()
    # Missingness is informative: fold the flags into numeric features.
    X["fleet_availability"] = X["fleet_availability"].fillna(-1.0)
    X["fleet_downtime"] = X["fleet_downtime"].fillna(-1.0)
    X["fleet_maintenance"] = X["fleet_maintenance"].fillna(-1.0)
    X["blast_delay_same_day"] = X["blast_delay_same_day"].fillna(-1.0)
    X["blast_delay_last_3d"] = X["blast_delay_last_3d"].fillna(-1.0)
    X["rainfall_1d"] = X["rainfall_1d"].fillna(0.0)
    X["rainfall_7d"] = X["rainfall_7d"].fillna(0.0)
    X["rainfall_30d"] = X["rainfall_30d"].fillna(0.0)
    return X[FEATURE_COLUMNS].astype(float).values, X[TARGET].astype(float).values


def build_models() -> dict[str, object]:
    return {
        "xgboost": XGBRegressor(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9,
            random_state=RANDOM_STATE, eval_metric="rmse",
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=300, random_state=RANDOM_STATE, min_samples_leaf=3,
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=4,
            random_state=RANDOM_STATE,
        ),
    }


def main() -> int:
    frame = pd.read_parquet(FEATURES_PATH)
    train_df, test_df, cutoff = time_aware_split(frame)
    X_train, y_train = prepare(train_df)
    X_test, y_test = prepare(test_df)

    print(f"Train rows: {len(train_df)}, Test rows: {len(test_df)} (dates >= {cutoff.date()})")

    # Column statistics summary for risk thresholds
    for col in ["rainfall_1d", "rainfall_7d", "rainfall_30d", "fleet_downtime"]:
        if col in frame.columns:
            s = frame[col].dropna()
            print(f"Column [{col}] -> Min: {s.min():.2f}, Max: {s.max():.2f}, Avg: {s.mean():.2f}")


    results: dict[str, dict] = {}
    for name, model in build_models().items():
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        results[name] = {
            "rmse": float(root_mean_squared_error(y_test, preds)),
            "mae": float(mean_absolute_error(y_test, preds)),
        }

    best = min(results, key=lambda n: results[n]["rmse"])
    best_model = build_models()[best].fit(X_train, y_train)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, MODEL_PATH)
    META_PATH.write_text(
        json.dumps(
            {
                "model_name": best,
                "model_version": "v1",
                "feature_columns": FEATURE_COLUMNS,
                "target": TARGET,
                "split": "time-aware",
                "train_until": str(cutoff.date()),
                "test_rows": int(len(test_df)),
                "test_metrics": results,
                "data_type": "statistical_prediction",
            },
            indent=2,
        )
    )
    print(f"Selected: {best} (RMSE {results[best]['rmse']:.1f})")
    print(f"Artifact: {MODEL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
