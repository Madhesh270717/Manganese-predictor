"""Resource Estimation API — Phase 13 (PRD Sections 8–9)."""

from fastapi import APIRouter, HTTPException

from app.services.resource_estimation_service import (
    get_all_resource_estimates,
    get_resource_estimate,
)

router = APIRouter(prefix="/reserve", tags=["resource-estimation"])


@router.get("/resource-estimate/{zone_id}")
def resource_estimate_for_zone(zone_id: str) -> dict:
    """Single zone resource estimate (statistical, NOT certified)."""
    result = get_resource_estimate(zone_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")
    return result


@router.get("/resource-estimate")
def resource_estimate_all() -> dict:
    """All zones — insufficient_data zones appear flagged, never omitted."""
    return get_all_resource_estimates()
