"""Alternative zone evaluation API — Phase 19 (PRD Section 19)."""

from fastapi import APIRouter, HTTPException

from ml.pipelines.optimization.candidate_zones import select_candidate_zones
from ml.pipelines.optimization.risk_trigger import detect_schedule_risks
from ml.pipelines.optimization.zone_comparator import rank_candidates

router = APIRouter(prefix="/optimization", tags=["optimization-alternatives"])


@router.get("/risks")
def schedule_risks() -> dict:
    """Risk triggers for the current schedule (weather + shortfall)."""
    from app.services.production_prediction_service import _current_schedule

    triggers = detect_schedule_risks(_current_schedule())
    return {
        "count": len(triggers),
        "triggers": triggers,
    }


@router.get("/alternatives/{equipment_id}")
def alternatives_for_equipment(equipment_id: str) -> dict:
    """Ranked candidate alternative zones for one at-risk equipment."""
    from app.services.production_prediction_service import _current_schedule

    schedule = _current_schedule()
    current_zone = next(
        (e["zone_id"] for e in schedule if e["equipment_id"] == equipment_id),
        None,
    )
    if current_zone is None:
        raise HTTPException(status_code=404, detail=f"Equipment not scheduled: {equipment_id}")

    candidates = select_candidate_zones(equipment_id, current_zone)
    ranked = rank_candidates(equipment_id, candidates, schedule)

    return {
        "equipment_id": equipment_id,
        "current_zone_id": current_zone,
        "candidate_count": len(ranked),
        "ranked_candidates": ranked,
    }
