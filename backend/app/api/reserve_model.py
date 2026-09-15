"""Reserve Prospectivity API — Phase 12 (PRD Sections 6–9)."""

from fastapi import APIRouter, HTTPException

from app.services.reserve_model_service import (
    get_all_zones_prospectivity,
    get_prospectivity,
)

router = APIRouter(prefix="/reserve", tags=["reserve-prospectivity"])


@router.get("/prospectivity/{zone_id}")
def prospectivity_for_zone(zone_id: str) -> dict:
    """Single zone prospectivity (statistical, NOT confirmed reserve)."""
    result = get_prospectivity(zone_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")
    return result


@router.get("/prospectivity")
def prospectivity_all() -> dict:
    """All-zone prospectivity for the map view (Phase 25)."""
    return get_all_zones_prospectivity()
