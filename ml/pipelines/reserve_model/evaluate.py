"""Reserve Prospectivity model evaluation — Phase 12.

Precision, Recall, ROC-AUC (CV-based, honest about n=20), plus a spatial
ranking sanity check: the known high-prospectivity cluster must rank above
the known low zones. Writes evaluation_report.md.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from app.services.synthetic.geological_generator import HIGH_PROSPECTIVITY_ZONES
from ml.pipelines.reserve_model.train import (
    FEATURE_COLUMNS,
    FEATURES_PATH,
    MODEL_PATH,
    META_PATH,
    N_FOLDS,
    RANDOM_STATE,
    build_proxy_labels,
    prepare,
)

REPORT_PATH = Path(__file__).resolve().parent / "evaluation_report.md"

# Zones known to be background (no cluster membership, no drilling signal).
LOW_ZONES = ["A1", "A2", "A3", "A4", "A5", "D4", "D5"]


def cross_val_metrics(X: np.ndarray, y: np.ndarray, model) -> dict:
    """CV predicted probabilities via the deployed model (refit per fold)."""
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    probas = np.zeros(len(y))
    for train_idx, val_idx in skf.split(X, y):
        # Refit an equivalent model per fold for honest out-of-fold scores.
        from xgboost import XGBClassifier
        from sklearn.ensemble import RandomForestClassifier

        if isinstance(model, XGBClassifier):
            fold_model = XGBClassifier(
                n_estimators=200, max_depth=3, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                eval_metric="logloss", random_state=RANDOM_STATE,
            )
        else:
            fold_model = RandomForestClassifier(
                n_estimators=300, random_state=RANDOM_STATE, class_weight="balanced"
            )
        fold_model.fit(X[train_idx], y[train_idx])
        probas[val_idx] = fold_model.predict_proba(X[val_idx])[:, 1]

    preds = (probas >= 0.5).astype(int)
    from sklearn.metrics import roc_auc_score

    try:
        auc = float(roc_auc_score(y, probas))
    except ValueError:
        # Single-class validation fold — undefined AUC, report honestly.
        auc = float("nan")

    return {
        "precision": float(precision_score(y, preds, zero_division=0)),
        "recall": float(recall_score(y, preds, zero_division=0)),
        "roc_auc": auc,
    }


def spatial_ranking_check(frame: pd.DataFrame, probas: np.ndarray, zone_ids: list[str]) -> dict:
    """Sanity: cluster zones must rank above known-low zones on average."""
    score_by_zone = dict(zip(zone_ids, probas))
    cluster_scores = [score_by_zone[z] for z in HIGH_PROSPECTIVITY_ZONES if z in score_by_zone]
    low_scores = [score_by_zone[z] for z in LOW_ZONES if z in score_by_zone]

    cluster_mean = float(np.mean(cluster_scores))
    low_mean = float(np.mean(low_scores))
    return {
        "cluster_mean_score": round(cluster_mean * 100, 1),
        "low_zone_mean_score": round(low_mean * 100, 1),
        "cluster_ranks_above_low": cluster_mean > low_mean,
        "best_cluster_zone": max(HIGH_PROSPECTIVITY_ZONES, key=lambda z: score_by_zone.get(z, 0)),
    }


def main() -> int:
    frame = pd.read_parquet(FEATURES_PATH)
    X, y, zone_ids = prepare(frame)

    artifact = joblib.load(MODEL_PATH)
    model = artifact["model"]
    temperature = artifact.get("calibration_temperature", 0.5)
    metrics = cross_val_metrics(X, y, model)

    # Deployed-model scores on all zones (fit-on-all, reported as in-sample).
    from ml.pipelines.reserve_model.train import apply_sigmoid

    raw_probas = model.predict_proba(X)[:, 1]
    probas = apply_sigmoid(raw_probas, temperature)
    ranking = spatial_ranking_check(frame, probas, zone_ids)

    meta = __import__("json").loads(META_PATH.read_text())

    lines = [
        "# Reserve Prospectivity Model — Evaluation Report (Phase 12)",
        "",
        f"- Model: {meta['model_name']} (version {meta['model_version']})",
        f"- Zones: {len(zone_ids)} (small synthetic sample — metrics are indicative only)",
        f"- Label strategy: {meta['label_strategy']} (see README.md for the honest proxy-label caveat)",
        f"- CV folds: 4 (4 positive labels — one per fold; 5 folds would give single-class folds)",
        f"- Calibration: {meta.get('calibration', 'none')} (temperature {meta.get('calibration_temperature', '-')})",
        "",
        "## Cross-validated metrics (4-fold stratified)",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Precision | {metrics['precision']:.3f} |",
        f"| Recall | {metrics['recall']:.3f} |",
        f"| ROC-AUC | {metrics['roc_auc']:.3f} |",
        "",
        "> With n=20, these numbers are honest but noisy. The spatial ranking",
        "> check below is the primary face-validity signal for this prototype.",
        "",
        "## Spatial ranking sanity check",
        "",
        "| Check | Value |",
        "| --- | --- |",
        f"| Cluster (B2/B3/C2/C3) mean score | {ranking['cluster_mean_score']}% |",
        f"| Known-low zones mean score | {ranking['low_zone_mean_score']}% |",
        f"| Cluster ranks above low zones | {ranking['cluster_ranks_above_low']} |",
        f"| Top cluster zone | {ranking['best_cluster_zone']} |",
        "",
        "## Zone scores (deployed model, in-sample)",
        "",
        "| Zone | Prospectivity |",
        "| --- | --- |",
    ]
    for zone, proba in sorted(zip(zone_ids, probas), key=lambda t: -t[1]):
        lines.append(f"| {zone} | {proba * 100:.1f}% |")

    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(f"Report written: {REPORT_PATH}")
    print(f"Metrics: {metrics}")
    print(f"Ranking: {ranking}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
