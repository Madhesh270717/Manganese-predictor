"""Explainability service — Phase 17 (PRD Section 16, NFR Section 41).

Instance-specific shortfall attribution: builds the feature row(s) for the
schedule (reusing Phase 15's feature construction), computes SHAP values,
and rolls them up into PRD-aligned categories. Works for the current
schedule and hypothetical schedules — the optimizer (Phase 18+) and the
chatbot (Phase 29) consume the same payload.
"""

from __future__ import annotations

from ml.pipelines.production_model.explain import explain_prediction
from ml.pipelines.production_model.feature_category_map import shortfall_contributors


def _average_feature_row(schedule: list[dict]) -> dict | None:
    """Mean feature vector across the schedule's unit-days (weighted by
    planned output) — a single representative instance for SHAP.

    Returns a feature dict or None if the schedule is empty.
    """
    from app.services.production_prediction_service import _build_feature_rows

    dates = sorted({e["date"] for e in schedule})
    if not dates:
        return None
    frame = _build_feature_rows(schedule, dates)
    if frame.empty:
        return None

    # Weight by planned production so big shifts dominate the explanation.
    weights = frame["planned_production"].clip(lower=0)
    if weights.sum() == 0:
        weights = None

    averaged = {}
    for col in frame.columns:
        if col in ("zone_id", "date"):
            continue
        values = frame[col].astype(float)
        if weights is not None:
            averaged[col] = float((values * weights).sum() / weights.sum())
        else:
            averaged[col] = float(values.mean())
    return averaged


def get_shortfall_contributors(schedule: list[dict] | None = None) -> dict:
    """Ranked, categorized, normalized contributor breakdown.

    Args:
        schedule: optional hypothetical schedule (None → current).
    """
    from app.services.production_prediction_service import (
        _current_schedule,
        predict_current,
        predict_production,
    )

    if schedule is None:
        schedule = _current_schedule()
        prediction = predict_current()
    elif not schedule:
        return {"error": "empty schedule"}
    else:
        prediction = predict_production(schedule)

    row = _average_feature_row(schedule)
    if row is None:
        return {"error": "empty schedule"}

    shap_rows = explain_prediction(row)
    contributors = shortfall_contributors(shap_rows)

    return {
        "predicted_tonnes": prediction["predicted_tonnes"],
        "target_tonnes": prediction["target_tonnes"],
        "shortfall_tonnes": round(prediction["target_tonnes"] - prediction["predicted_tonnes"], 1),
        "contributors": contributors,
        "top_contributor": contributors[0]["label"] if contributors else None,
        "model_version": prediction.get("model_version"),
        "data_type": "shap_shortfall_explanation",
    }
