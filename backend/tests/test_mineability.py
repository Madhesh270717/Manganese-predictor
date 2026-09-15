"""Tests for mineability scoring — Phase 14."""

from datetime import date

import pytest

from ml.pipelines.mineability_model.score import (
    WEIGHTS,
    access_score,
    classify,
    composite_score,
    equipment_score,
    resource_tier_score,
    terrain_score,
    weather_score,
)
from app.services.mineability_service import get_mineability


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_classification_thresholds():
    assert classify(90.0) == "Recommended"
    assert classify(70.0) == "Recommended"
    assert classify(69.9) == "Conditional"
    assert classify(45.0) == "Conditional"
    assert classify(44.9) == "Avoid-Postpone"


def test_component_score_ranges():
    assert terrain_score(3.0, "GOOD") > terrain_score(18.0, "POOR")
    assert access_score(2.0, "GOOD") > access_score(10.0, "POOR")
    assert weather_score(0.0) == 100.0
    assert weather_score(110.0) == 0.0
    assert equipment_score(0.9) == 90.0
    assert resource_tier_score("HIGH") > resource_tier_score("LOW")


def test_b3_mineability_close_to_prd_example():
    # PRD §11: Prospectivity 89, Resource HIGH, Terrain GOOD, Access GOOD,
    # Weather GOOD, Equipment HIGH -> Mineability Score 86%.
    result = get_mineability("B3")
    assert result is not None
    assert result["classification"] == "Recommended"
    assert 75.0 <= result["mineability_score"] <= 95.0
    assert result["prospectivity"] >= 85.0  # Phase 12 B3 ≈ 93.1
    # Cluster slopes U(2,8)° -> terrain base 75 or 90, GOOD access +0.
    assert result["components"]["terrain"] >= 70.0
    assert result["components"]["access"] >= 85.0
    assert result["components"]["equipment_availability"] >= 80.0
    assert "prospectivity" in result["components"]


def test_a1_at_risk_zone_scores_worse():
    # A1: POOR roads + heavy demo rain + degraded EX-04 fleet.
    a1 = get_mineability("A1")
    b3 = get_mineability("B3")
    assert a1 is not None and b3 is not None
    assert a1["mineability_score"] < b3["mineability_score"]
    assert a1["classification"] != "Recommended"


def test_score_is_dynamic_when_weather_changes():
    """Score must shift when the underlying weather changes (Phase 18+ need)."""
    from app.services.mineability_service import composite_score as svc_composite

    base = svc_composite(
        prospectivity=90.0,
        resource_confidence="MEDIUM",
        slope_degrees=5.0,
        accessibility="GOOD",
        haul_km=2.0,
        road_condition="GOOD",
        rainfall_1d=0.0,
        fleet_availability=0.9,
    )
    rainy = svc_composite(
        prospectivity=90.0,
        resource_confidence="MEDIUM",
        slope_degrees=5.0,
        accessibility="GOOD",
        haul_km=2.0,
        road_condition="GOOD",
        rainfall_1d=110.0,
        fleet_availability=0.9,
    )
    assert rainy["mineability_score"] < base["mineability_score"]
    # Weather carries 0.20 weight; 0→110mm drops the weather component 100 pts.
    assert abs(base["mineability_score"] - rainy["mineability_score"]) == pytest.approx(20.0, abs=0.2)


def test_component_breakdown_in_payload():
    result = get_mineability("B3")
    for key in ("prospectivity", "resource_availability", "terrain", "access", "weather", "equipment_availability"):
        assert key in result["components"]
    assert result["dynamic"] is True
    assert "weights" in result


def test_unknown_zone_returns_none():
    assert get_mineability("ZZ9") is None
