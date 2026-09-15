"""Tests for production prediction service — Phase 15."""

from datetime import date, timedelta

import pytest

from app.services.production_prediction_service import (
    predict_current,
    predict_production,
)


def test_current_prediction_below_target():
    result = predict_current()
    # The schedule splits 82,000 across 30 days/2 shifts with rounding, so
    # the planned total lands within a few tonnes of the target.
    assert result["target_tonnes"] == pytest.approx(82000.0, abs=50.0)
    assert result["predicted_tonnes"] < result["target_tonnes"]
    # Meaningfully below: at least a few thousand tonnes shortfall.
    assert result["target_tonnes"] - result["predicted_tonnes"] > 2000.0
    assert result["data_type"] == "statistical_prediction"
    assert "model_version" in result


def test_current_prediction_reasonably_close_to_prd_example():
    """PRD §13: Target 82,000t -> Predicted ~74,600t.

    The model genuinely computes from seeded conditions; we validate it
    lands in a sensible band around the PRD figure without hardcoding.
    """
    result = predict_current()
    predicted = result["predicted_tonnes"]
    # A generous band: 60k–80k captures the demo's shortfall narrative.
    assert 60000.0 <= predicted <= 82000.0
    # Per-zone breakdown exists and sums to the total.
    zone_sum = sum(z["predicted"] for z in result["per_zone"])
    assert abs(zone_sum - predicted) < 5.0


def test_hypothetical_move_ex04_to_b3_improves_prediction():
    """The 'what if EX-04 were in Zone B' scenario must predict UP."""
    baseline = predict_current()
    moved = _scenario_with_ex04_in("B3")
    assert moved["predicted_tonnes"] > baseline["predicted_tonnes"]


def test_hypothetical_move_into_at_risk_zone_reduces_prediction():
    """Moving a unit INTO rainy A1 (dry->wet) must reduce prediction."""
    baseline = predict_current()
    from app.services.production_prediction_service import _current_schedule

    schedule = _current_schedule()
    for entry in schedule:
        if entry["equipment_id"] == "T-06":  # currently B3 (dry)
            entry["zone_id"] = "A1"  # into the 110mm storm
    moved = predict_production(schedule)
    assert moved["predicted_tonnes"] < baseline["predicted_tonnes"]


def _scenario_with_ex04_in(target_zone: str) -> dict:
    """Build the current schedule with EX-04 reassigned to target_zone."""
    from app.services.production_prediction_service import _current_schedule

    schedule = _current_schedule()
    for entry in schedule:
        if entry["equipment_id"] == "EX-04":
            entry["zone_id"] = target_zone
    return predict_production(schedule)


def test_empty_schedule_rejected_by_service_shape():
    # Service-level guard: an empty schedule has no dates.
    with pytest.raises(ValueError):
        predict_production([])
