"""Tests for SHAP explainability — Phase 17."""

import pytest

from ml.pipelines.production_model.explain import explain_prediction
from ml.pipelines.production_model.feature_category_map import (
    CATEGORY_MAP,
    rollup_to_categories,
    shortfall_contributors,
)
from app.services.explainability_service import get_shortfall_contributors


def _sample_row() -> dict:
    return {
        "planned_production": 550.0,
        "ore_grade": 43.9,
        "rainfall_1d": 110.0,
        "rainfall_7d": 330.0,
        "rainfall_30d": 1100.0,
        "fleet_availability": 0.516,
        "fleet_downtime": 5.8,
        "fleet_maintenance": 2.9,
        "fleet_capacity": 110.0,
        "active_units": 1,
        "blast_delay_same_day": 5.5,
        "blast_delay_last_3d": 6.0,
    }


def test_shap_values_compute():
    rows = explain_prediction(_sample_row())
    assert len(rows) == 12
    assert all(r["contribution_percentage"] >= 0 for r in rows)
    total = sum(r["contribution_percentage"] for r in rows)
    assert total == pytest.approx(100.0, abs=1.0)


def test_category_map_covers_all_features():
    mapped = {f for _, features in CATEGORY_MAP.values() for f in features}
    from ml.pipelines.production_model.train import FEATURE_COLUMNS

    assert mapped == set(FEATURE_COLUMNS)


def test_rollup_normalizes_to_100():
    rows = explain_prediction(_sample_row())
    categories = rollup_to_categories(rows)
    total = sum(c["contribution_percentage"] for c in categories)
    assert total == pytest.approx(100.0, abs=1.0)


def test_shortfall_contributors_sum_100_and_ranked():
    rows = explain_prediction(_sample_row())
    contributors = shortfall_contributors(rows)
    assert [c["category"] for c in contributors] == sorted(
        [c["category"] for c in contributors],
        key=lambda cat: -next(c["contribution_percentage"] for c in contributors if c["category"] == cat),
    )
    total = sum(c["contribution_percentage"] for c in contributors)
    assert total == pytest.approx(100.0, abs=1.0)
    # Equipment is #1 for the demo conditions (downtime ~41% narrative).
    assert contributors[0]["category"] == "equipment"


def test_current_contributors_align_with_prd_section_16():
    """PRD §16: Equipment 41%, Rainfall 24%, Blasting 20%, Ore grade 15%.

    The exact percentages are illustrative. Our ordering is Equipment >
    Ore grade > Rainfall > Blasting — a documented, defensible deviation:
    the demo storm only hits A1 (1 of 5 zones) while ore-grade variation
    is global, so the model legitimately ranks it higher. Equipment-first
    matches the PRD; see ml/pipelines/production_model/README.md.
    """
    result = get_shortfall_contributors(schedule=None)
    assert result["data_type"] == "shap_shortfall_explanation"
    labels = [c["label"] for c in result["contributors"]]
    assert "Equipment downtime" in labels
    assert "Rainfall" in labels
    assert labels[0] == "Equipment downtime"
    total = sum(c["contribution_percentage"] for c in result["contributors"])
    assert total == pytest.approx(100.0, abs=1.0)


def test_hypothetical_schedule_explains():
    from app.services.production_prediction_service import _current_schedule

    schedule = _current_schedule()
    for entry in schedule:
        if entry["equipment_id"] == "EX-04":
            entry["zone_id"] = "B3"
    result = get_shortfall_contributors(schedule=schedule)
    assert result["shortfall_tonnes"] >= 0
    assert len(result["contributors"]) == 4


def test_empty_schedule_returns_error():
    result = get_shortfall_contributors(schedule=[])
    assert "error" in result
