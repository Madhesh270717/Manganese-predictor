"""Mineability API — Phase 14 (PRD Sections 10–11)."""

from fastapi import APIRouter, HTTPException

from app.services.mineability_service import get_all_mineability, get_mineability

router = APIRouter(prefix="/mineability", tags=["mineability-score"])


@router.get("/{zone_id}")
def mineability_for_zone(zone_id: str) -> dict:
    """Live mineability breakdown for one zone."""
    result = get_mineability(zone_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")
    return result


@router.get("")
def mineability_all() -> dict:
    """All-zone mineability (live, sorted desc)."""
    return get_all_mineability()
