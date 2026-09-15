"""Recommendation API — Phase 20 (PRD Sections 20–21, 36)."""

from fastapi import APIRouter, HTTPException

from app.services.recommendation_service import (
    generate_all_recommendations,
    generate_recommendation,
    get_schedule_comparison,
)

router = APIRouter(prefix="/recommendations", tags=["reallocation-recommendations"])


@router.get("/{equipment_id}")
def recommendation_for_equipment(equipment_id: str) -> dict:
    """Single equipment reallocation recommendation."""
    result = generate_recommendation(equipment_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"No recommendation: equipment {equipment_id} not at risk"
        )
    return result


@router.get("")
def all_recommendations() -> dict:
    """Mine-wide scan of all at-risk equipment (prioritized)."""
    return generate_all_recommendations()


@router.get("/{equipment_id}/schedule-comparison")
def schedule_comparison(equipment_id: str) -> dict:
    """Before/after schedule detail for the comparison view (Phase 27)."""
    return get_schedule_comparison(equipment_id)
