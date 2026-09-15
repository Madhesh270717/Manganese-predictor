"""Tests for alternative zone evaluation — Phase 19."""

from app.services.production_prediction_service import _current_schedule
from ml.pipelines.optimization.candidate_zones import select_candidate_zones
from ml.pipelines.optimization.risk_trigger import detect_schedule_risks
from ml.pipelines.optimization.zone_comparator import (
    evaluate_candidate,
    rank_candidates,
)


def test_risk_trigger_fires_for_ex04():
    schedule = _current_schedule()
    triggers = detect_schedule_risks(schedule)
    ex04 = [t for t in triggers if t["equipment_id"] == "EX-04"]
    assert ex04, "EX-04 in A1 must trigger (110mm demo storm)"
    assert ex04[0]["current_zone_id"] == "A1"
    assert ex04[0]["severity"] == "HIGH"
    assert "weather" in ex04[0]["risk_reason"]


def test_candidates_exclude_current_zone():
    candidates = select_candidate_zones("EX-04", "A1")
    assert "A1" not in candidates
    assert len(candidates) > 0


def test_candidates_have_ore_access_and_reasonable_haul():
    candidates = select_candidate_zones("EX-04", "A1")
    # Filtering is documented: prospectivity >= 40 OR resource estimate,
    # haul <= 12km. A handful of zones, not all 20.
    assert len(candidates) <= 10
    assert "B3" in candidates, "high-prospectivity B3 must be a candidate"


def test_candidate_evaluation_returns_full_criteria():
    schedule = _current_schedule()
    result = evaluate_candidate("EX-04", "B3", schedule)
    for key in ("production_risk", "distance", "equipment", "shortfall_delta"):
        assert key in result["criteria"]
        assert 0.0 <= result["criteria"][key] <= 100.0
    assert result["total_score"] > 0
    assert result["mineability"]["classification"] == "Recommended"


def test_ranking_sorted_and_cluster_zones_top():
    """Ranking must be sorted desc, with the Phase 5/6 cluster on top.

    Documented deviation: C3 narrowly outranks B3 (its haul is ~2km vs
    B3's ~4.4km, with near-identical prospectivity/equipment) — the
    PRD's "move to Zone B" is narrative; the data-driven ranking is
    C3 > C2 > B3 > B2. Phase 20 will present the top candidate with
    this explanation rather than forcing Zone B.
    """
    schedule = _current_schedule()
    candidates = select_candidate_zones("EX-04", "A1")
    ranked = rank_candidates("EX-04", candidates, schedule)
    scores = [r["total_score"] for r in ranked]
    assert scores == sorted(scores, reverse=True)
    top_zones = {r["candidate_zone_id"] for r in ranked[:3]}
    assert top_zones <= {"B2", "B3", "C2", "C3"}
    assert "B3" in top_zones


def test_shortfall_delta_positive_for_b3():
    """Moving EX-04 to B3 must score a meaningful shortfall improvement."""
    schedule = _current_schedule()
    result = evaluate_candidate("EX-04", "B3", schedule)
    assert result["criteria"]["shortfall_delta"] > 50.0
