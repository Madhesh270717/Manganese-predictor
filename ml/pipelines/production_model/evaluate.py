"""Production Prediction model evaluation — Phase 15.

MAE / RMSE / MAPE on the time-held-out test set + top feature importances
(full SHAP comes in Phase 17). Writes evaluation_report.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

from ml.pipelines.production_model.train import (
    FEATURES_PATH,
    META_PATH,
    MODEL_PATH,
    prepare,
    time_aware_split,
)

REPORT_PATH = Path(__file__).resolve().parent / "evaluation_report.md"


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true > 1.0  # MAPE undefined near zero production days
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def main() -> int:
    frame = pd.read_parquet(FEATURES_PATH)
    train_df, test_df, cutoff = time_aware_split(frame)
    X_test, y_test = prepare(test_df)

    model = joblib.load(MODEL_PATH)
    preds = model.predict(X_test)

    metrics = {
        "mae": float(mean_absolute_error(y_test, preds)),
        "rmse": float(root_mean_squared_error(y_test, preds)),
        "mape_pct": mape(y_test, preds),
    }

    meta = json.loads(META_PATH.read_text())

    # Top feature importances (high-level; SHAP in Phase 17).
    if hasattr(model, "feature_importances_"):
        importances = sorted(
            zip(meta["feature_columns"], model.feature_importances_),
            key=lambda t: -t[1],
        )
        top_features = [(name, round(imp, 4)) for name, imp in importances[:5]]
    else:
        top_features = []

    lines = [
        "# Production Prediction Model — Evaluation Report (Phase 15)",
        "",
        f"- Model: {meta['model_name']} (version {meta['model_version']})",
        f"- Split: time-aware — trained on dates < {meta['train_until']}, "
        f"tested on the most recent {meta['test_rows']} rows",
        "",
        "## Held-out metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| MAE (t/day) | {metrics['mae']:.1f} |",
        f"| RMSE (t/day) | {metrics['rmse']:.1f} |",
        f"| MAPE | {metrics['mape_pct']:.1f}% |",
        "",
        "> The test window contains the Phase 8 demo storm (A1 110mm rain),",
        "> so these metrics genuinely reflect the model's ability to predict",
        "> production under the event the demo narrative depends on.",
        "",
        "## Top feature importances (high-level)",
        "",
        "| Feature | Importance |",
        "| --- | --- |",
    ]
    for name, imp in top_features:
        lines.append(f"| {name} | {imp} |")

    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(f"Report written: {REPORT_PATH}")
    print(f"Metrics: {metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
