"""Tests for the recommendation engine — Phase 20."""

import pytest

from ml.pipelines.optimization.objective import (
    WEIGHTS,
    movement_penalty,
    production_score,
    risk_score,
    score_schedule,
    shortfall_penalty,
    utilization_score,
)
from app.services.recommendation_service import (
    generate_all_recommendations,
    generate_recommendation,
    get_schedule_comparison,
)


def test_objective_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_term_normalization_bounds():
    assert production_score(82000, 82000) == 100.0
    assert production_score(74600, 82000) == pytest.approx(91.0, abs=0.5)
    assert utilization_score(0.9) == 90.0
    assert risk_score([90.0, 80.0]) == pytest.approx(15.0, abs=0.1)
    assert movement_penalty(10.0) == 50.0
    assert movement_penalty(100.0) == 100.0
    assert shortfall_penalty(9.0) == pytest.approx(60.0, abs=0.1)


def test_objective_score_structure():
    result = score_schedule(
        predicted_tonnes=75000,
        target_tonnes=82000,
        mean_availability=0.85,
        mineability_scores=[87.0, 70.0, 60.0],
        total_move_km=5.0,
        shortfall_percentage=8.5,
    )
    assert set(result["terms"]) == set(WEIGHTS)
    assert "objective_score" in result


def test_demo_recommendation_moves_ex04_away_from_a1():
    rec = generate_recommendation("EX-04")
    assert rec is not None
    assert rec["alert"] == "PRODUCTION RISK DETECTED"
    assert rec["action"] == "MOVE"
    assert rec["equipment_id"] == "EX-04"
    assert rec["from_zone"] == "A1"
    assert rec["to_zone"] != "A1"
    assert rec["status"] == "pending_approval"
    assert rec["reason"] == "High rainfall predicted in the current zone"


def test_expected_impact_computed_from_models():
    rec = generate_recommendation("EX-04")
    impact = rec["expected_impact"]
    # Moving out of the rain improves production and cuts shortfall.
    assert impact["production_after"] > impact["production_before"]
    assert impact["shortfall_after"] < impact["shortfall_before"]
    # Directionally consistent with PRD §21 (74,600 → ~81,300).
    assert 70000 < impact["production_before"] < 80000
    assert impact["production_after"] > impact["production_before"]


def test_all_recommendations_scan():
    result = generate_all_recommendations()
    assert result["count"] >= 1
    ids = {r["equipment_id"] for r in result["recommendations"]}
    assert "EX-04" in ids
    # All pending approval — nothing auto-applied (Phase 22 human-in-the-loop).
    assert all(r["status"] == "pending_approval" for r in result["recommendations"])


def test_schedule_comparison_structure():
    comparison = get_schedule_comparison("EX-04")
    assert comparison["equipment_id"] == "EX-04"
    assert comparison["moved_entries"] > 0
    assert set(comparison["before"]) == set(comparison["after"])
    assert comparison["shortfall_after"] < comparison["shortfall_before"]
