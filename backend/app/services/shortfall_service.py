"""Shortfall detection & risk classification — Phase 16 (PRD Sections 14–15).

Business logic wrapping Phase 15's production prediction: computes
shortfall (tonnes + %), classifies risk with the exact PRD §15 thresholds,
and builds the dashboard-ready summary. Works for both the current
schedule and hypothetical schedules (Phase 18–21 optimizer compares
"shortfall before" vs "shortfall after" by reusing this).
"""

from __future__ import annotations

# Exact PRD Section 15 thresholds.
LOW_THRESHOLD = 5.0  # 0–5% → LOW
MEDIUM_THRESHOLD = 15.0  # 5–15% → MEDIUM, >15% → HIGH

BAR_BLOCKS = 20  # progress-bar blocks for the frontend risk indicator
BAR_FULL_SCALE_PCT = 15.0  # 15% shortfall = full bar (HIGH boundary)


def calculate_shortfall(planned: float, predicted: float) -> dict:
    """shortfall_tonnes + shortfall_percentage (PRD §14)."""
    shortfall = planned - predicted
    percentage = (shortfall / planned * 100.0) if planned > 0 else 0.0
    return {
        "shortfall_tonnes": round(shortfall, 1),
        "shortfall_percentage": round(percentage, 2),
    }


def classify_risk(shortfall_percentage: float) -> str:
    """Exact PRD §15 thresholds: 0–5% LOW, 5–15% MEDIUM, >15% HIGH."""
    if shortfall_percentage < LOW_THRESHOLD:
        return "LOW"
    if shortfall_percentage <= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "HIGH"


def risk_bar_data(shortfall_percentage: float) -> dict:
    """Progress-bar visualization data for the frontend (Phase 26).

    PRD §15 renders a block-style risk bar; 20 blocks, filled
    proportionally to the shortfall with 15% = full bar.
    """
    filled = min(BAR_BLOCKS, round(shortfall_percentage / BAR_FULL_SCALE_PCT * BAR_BLOCKS))
    bar_text = "█" * filled + "░" * (BAR_BLOCKS - filled)
    return {
        "filled_blocks": filled,
        "total_blocks": BAR_BLOCKS,
        "bar_text": f"{bar_text} {classify_risk(shortfall_percentage)}",
    }


def _summary_from_prediction(prediction: dict, zone_id: str | None = None) -> dict:
    """Dashboard summary from a Phase 15 prediction payload."""
    if zone_id is None:
        planned = prediction["target_tonnes"]
        predicted = prediction["predicted_tonnes"]
    else:
        zone_row = next(
            (z for z in prediction["per_zone"] if z["zone_id"] == zone_id), None
        )
        if zone_row is None:
            return {}
        planned = zone_row["planned"]
        predicted = zone_row["predicted"]

    shortfall = calculate_shortfall(planned, predicted)
    risk = classify_risk(shortfall["shortfall_percentage"])
    return {
        "zone_id": zone_id,
        "target": round(planned, 1),
        "predicted": round(predicted, 1),
        **shortfall,
        "risk_level": risk,
        "risk_bar_visualization_data": risk_bar_data(shortfall["shortfall_percentage"]),
        "model_version": prediction.get("model_version"),
    }


def get_production_risk_summary(
    schedule: list[dict] | None = None,
    zone_id: str | None = None,
) -> dict:
    """Dashboard-ready risk summary (PRD §15) for current or hypothetical.

    Args:
        schedule: optional hypothetical schedule (None → current).
        zone_id: optional zone filter for per-zone shortfall.
    """
    from app.services.production_prediction_service import (
        predict_current,
        predict_production,
    )

    prediction = predict_production(schedule) if schedule is not None else predict_current()
    summary = _summary_from_prediction(prediction, zone_id)
    if not summary:
        return {
            "zone_id": zone_id,
            "error": "zone not in prediction breakdown",
        }
    summary["data_type"] = "statistical_shortfall"
    return summary


def get_current_shortfall(zone_id: str | None = None) -> dict:
    return get_production_risk_summary(schedule=None, zone_id=zone_id)


def get_scenario_shortfall(schedule: list[dict], zone_id: str | None = None) -> dict:
    return get_production_risk_summary(schedule=schedule, zone_id=zone_id)
