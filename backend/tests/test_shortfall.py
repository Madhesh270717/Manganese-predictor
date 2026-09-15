"""Tests for shortfall detection — Phase 16."""

import pytest

from app.services.shortfall_service import (
    calculate_shortfall,
    classify_risk,
    get_current_shortfall,
    get_scenario_shortfall,
    get_production_risk_summary,
    risk_bar_data,
)


def test_shortfall_calculation():
    result = calculate_shortfall(82000.0, 74600.0)
    assert result["shortfall_tonnes"] == 7400.0
    assert result["shortfall_percentage"] == pytest.approx(9.02, abs=0.01)


def test_risk_thresholds_exact_prd_section_15():
    # 0–5% LOW, 5–15% MEDIUM, >15% HIGH
    assert classify_risk(0.0) == "LOW"
    assert classify_risk(4.99) == "LOW"
    assert classify_risk(5.0) == "MEDIUM"
    assert classify_risk(9.02) == "MEDIUM"
    assert classify_risk(15.0) == "MEDIUM"
    assert classify_risk(15.01) == "HIGH"
    assert classify_risk(40.0) == "HIGH"


def test_demo_scenario_classifies_medium():
    """PRD §15: 7,400t / 82,000t ≈ 9.0% → MEDIUM."""
    summary = get_current_shortfall()
    assert summary["risk_level"] == "MEDIUM"
    assert 5.0 <= summary["shortfall_percentage"] <= 15.0
    assert summary["shortfall_tonnes"] > 0


def test_dashboard_summary_structure():
    summary = get_current_shortfall()
    for key in (
        "target",
        "predicted",
        "shortfall_tonnes",
        "shortfall_percentage",
        "risk_level",
        "risk_bar_visualization_data",
    ):
        assert key in summary
    bar = summary["risk_bar_visualization_data"]
    assert bar["filled_blocks"] <= bar["total_blocks"] == 20
    assert bar["bar_text"].endswith(summary["risk_level"])
    assert summary["data_type"] == "statistical_shortfall"


def test_zone_level_filter():
    summary = get_current_shortfall(zone_id="A1")
    assert summary["zone_id"] == "A1"
    # A1 has the 110mm storm — a very high per-zone shortfall.
    assert summary["shortfall_percentage"] > 15.0
    assert summary["risk_level"] == "HIGH"


def test_scenario_ex04_moved_reduces_shortfall():
    """The optimizer's core comparison: moving EX-04 to B3 must cut shortfall."""
    from app.services.production_prediction_service import _current_schedule

    baseline = get_current_shortfall()
    schedule = _current_schedule()
    for entry in schedule:
        if entry["equipment_id"] == "EX-04":
            entry["zone_id"] = "B3"
    moved = get_scenario_shortfall(schedule)

    assert moved["shortfall_tonnes"] < baseline["shortfall_tonnes"]
    assert moved["shortfall_percentage"] < baseline["shortfall_percentage"]


def test_risk_bar_full_at_high_boundary():
    bar = risk_bar_data(15.0)
    assert bar["filled_blocks"] == 20
    bar_low = risk_bar_data(2.0)
    assert bar_low["filled_blocks"] < bar["filled_blocks"]


def test_unknown_zone_filter_returns_error():
    summary = get_current_shortfall(zone_id="ZZ9")
    assert "error" in summary
