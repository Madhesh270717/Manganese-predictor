"""Tests for the recalculation loop — Phase 21."""

from app.services.recalculation_service import (
    MAX_CANDIDATE_ATTEMPTS,
    _PENDING_RECOMMENDATIONS,
    read_history,
    run_recalculation_cycle,
)


def test_demo_cycle_produces_recommendation():
    _PENDING_RECOMMENDATIONS.clear()
    result = run_recalculation_cycle()
    assert result["outcome"] == "recommended"
    rec = result["recommendation"]
    assert rec["equipment_id"] == "EX-04"
    assert rec["from_zone"] == "A1"
    assert rec["to_zone"] != "A1"
    assert result["log"]["new_shortfall"] < result["log"]["previous_shortfall"]


def test_duplicate_recommendation_suppressed():
    """Second cycle while pending exists must skip regeneration."""
    _PENDING_RECOMMENDATIONS.clear()
    first = run_recalculation_cycle()
    assert first["outcome"] == "recommended"

    second = run_recalculation_cycle()
    assert second["outcome"] == "recommended"
    assert second.get("skipped_duplicate") is True
    assert "skipped" in second["log"]["detail"]


def test_no_improvement_branch_reachable():
    """Genuine branching: force candidates that don't help.

    Monkeypatch the shortfall lookup so every candidate reports WORSE
    shortfall — the loop must try up to MAX_CANDIDATE_ATTEMPTS and then
    honestly report no_improvement.
    """
    import app.services.recalculation_service as svc

    _PENDING_RECOMMENDATIONS.clear()
    original = svc._shortfall_for_candidate

    def worse(equipment_id, to_zone):
        return 99999.0

    svc._shortfall_for_candidate = worse
    try:
        result = run_recalculation_cycle()
    finally:
        svc._shortfall_for_candidate = original

    assert result["outcome"] == "no_improvement"
    assert result["tried_candidates"] == MAX_CANDIDATE_ATTEMPTS
    assert "did not reduce shortfall" in result["log"]["detail"]


def test_stable_schedule_exits_cleanly():
    """No risk → clean exit without recommendation."""
    import app.services.recalculation_service as svc

    _PENDING_RECOMMENDATIONS.clear()
    original = svc._risk_reason

    def no_risk():
        return None

    svc._risk_reason = no_risk
    original_detect = None
    try:
        # Also stub detect_schedule_risks used inside run_recalculation_cycle.
        from ml.pipelines.optimization import risk_trigger

        original_detect = risk_trigger.detect_schedule_risks
        risk_trigger.detect_schedule_risks = lambda schedule: []
        result = run_recalculation_cycle()
    finally:
        svc._risk_reason = original
        if original_detect is not None:
            risk_trigger.detect_schedule_risks = original_detect

    assert result["outcome"] == "stable"
    assert result["log"]["trigger_reason"] == "schedule stable"


def test_history_logs_cycles():
    _PENDING_RECOMMENDATIONS.clear()
    run_recalculation_cycle()
    history = read_history(limit=10)
    assert len(history) >= 1
    assert history[-1]["outcome"] in ("recommended", "stable", "no_improvement")
    assert "triggered_at" in history[-1]
    assert "trigger_reason" in history[-1]
