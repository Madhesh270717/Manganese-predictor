"""Equipment Reallocation Recommendation — Phase 20 (PRD Sections 20–21, 36).

Turns Phase 19's ranked candidate comparison into the concrete
human-readable "MOVE EX-04, Zone A → Zone B" recommendation, with
before/after figures computed from real model calls (Phase 15/16) and
reason text generated from the actual risk trigger.
"""

from __future__ import annotations

from ml.pipelines.optimization.candidate_zones import select_candidate_zones
from ml.pipelines.optimization.risk_trigger import detect_schedule_risks
from ml.pipelines.optimization.zone_comparator import rank_candidates
from ml.pipelines.optimization.objective import score_schedule


def _current_schedule() -> list[dict]:
    from app.services.production_prediction_service import _current_schedule

    return _current_schedule()


def _risk_reason(equipment_id: str, schedule: list[dict]) -> str:
    """Human-readable reason from the actual trigger, never hardcoded."""
    triggers = detect_schedule_risks(schedule)
    match = next((t for t in triggers if t["equipment_id"] == equipment_id), None)
    if match is None:
        return "production risk detected"
    if match["risk_reason"].startswith("weather"):
        return "High rainfall predicted in the current zone"
    if "shortfall" in match["risk_reason"]:
        return "Predicted production shortfall in the current zone"
    return match["risk_reason"]


def _expected_impact(
    equipment_id: str,
    from_zone: str,
    to_zone: str,
    schedule: list[dict],
) -> dict:
    """Before/after production + shortfall from real model calls."""
    from app.services.production_prediction_service import predict_current, predict_production
    from app.services.shortfall_service import calculate_shortfall

    before = predict_current()

    scenario = [dict(e) for e in schedule]
    for entry in scenario:
        if entry["equipment_id"] == equipment_id:
            entry["zone_id"] = to_zone
    after = predict_production(scenario)

    before_shortfall = calculate_shortfall(before["target_tonnes"], before["predicted_tonnes"])
    after_shortfall = calculate_shortfall(after["target_tonnes"], after["predicted_tonnes"])

    return {
        "production_before": before["predicted_tonnes"],
        "production_after": after["predicted_tonnes"],
        "shortfall_before": before_shortfall["shortfall_tonnes"],
        "shortfall_after": after_shortfall["shortfall_tonnes"],
        "shortfall_percentage_before": before_shortfall["shortfall_percentage"],
        "shortfall_percentage_after": after_shortfall["shortfall_percentage"],
    }


def generate_recommendation(equipment_id: str) -> dict | None:
    """Single-equipment recommendation (the PRD demo path)."""
    schedule = _current_schedule()
    triggers = detect_schedule_risks(schedule)
    trigger = next((t for t in triggers if t["equipment_id"] == equipment_id), None)
    if trigger is None:
        return None

    from_zone = trigger["current_zone_id"]
    candidates = select_candidate_zones(equipment_id, from_zone)
    if not candidates:
        return None

    ranked = rank_candidates(equipment_id, candidates, schedule)
    top = ranked[0]
    to_zone = top["candidate_zone_id"]
    impact = _expected_impact(equipment_id, from_zone, to_zone, schedule)

    return {
        "alert": "PRODUCTION RISK DETECTED",
        "action": "MOVE",
        "equipment_id": equipment_id,
        "from_zone": from_zone,
        "to_zone": to_zone,
        "reason": _risk_reason(equipment_id, schedule),
        "trigger": trigger,
        "ranking": ranked,
        "expected_impact": impact,
        "status": "pending_approval",
    }


def generate_all_recommendations() -> dict:
    """Mine-wide scan: prioritized recommendations for all at-risk units."""
    schedule = _current_schedule()
    triggers = detect_schedule_risks(schedule)

    recommendations = []
    for trigger in triggers:
        rec = generate_recommendation(trigger["equipment_id"])
        if rec is not None:
            recommendations.append(rec)

    recommendations.sort(
        key=lambda r: r["expected_impact"]["shortfall_before"]
        - r["expected_impact"]["shortfall_after"],
        reverse=True,
    )
    return {
        "count": len(recommendations),
        "recommendations": recommendations,
    }


def get_schedule_comparison(equipment_id: str, to_zone: str | None = None) -> dict:
    """Before/after schedule side-by-side (PRD §21 comparison view).

    The current schedule and the proposed schedule (equipment moved) with
    time blocks, equipment, zone, expected output.
    """
    from app.services.shortfall_service import get_current_shortfall

    schedule = _current_schedule()
    recommendation = generate_recommendation(equipment_id)
    if recommendation is None:
        return {"equipment_id": equipment_id, "error": "no recommendation"}

    to_zone = to_zone or recommendation["to_zone"]

    proposed = [dict(e) for e in schedule]
    moved_entries = 0
    for entry in proposed:
        if entry["equipment_id"] == equipment_id:
            entry["zone_id"] = to_zone
            moved_entries += 1

    def _summarize(entries: list[dict]) -> dict:
        by_day: dict[str, list[dict]] = {}
        for e in entries:
            by_day.setdefault(e["date"].isoformat(), []).append(
                {
                    "shift": e["shift"],
                    "equipment_id": e["equipment_id"],
                    "zone_id": e["zone_id"],
                    "expected_output": e["expected_output"],
                }
            )
        return by_day

    return {
        "equipment_id": equipment_id,
        "to_zone": to_zone,
        "moved_entries": moved_entries,
        "before": _summarize(schedule),
        "after": _summarize(proposed),
        "shortfall_before": get_current_shortfall()["shortfall_tonnes"],
        "shortfall_after": recommendation["expected_impact"]["shortfall_after"],
    }
