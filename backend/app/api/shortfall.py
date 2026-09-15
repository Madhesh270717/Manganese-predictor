"""Shortfall API — Phase 16 (PRD Sections 14–15)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import require_api_key
from app.services.shortfall_service import (
    get_current_shortfall,
    get_scenario_shortfall,
)

router = APIRouter(prefix="/production/shortfall", tags=["production-shortfall"])


class ScheduleEntry(BaseModel):
    date: date
    shift: str = Field(default="A", pattern="^[A-B]$")
    equipment_id: str
    zone_id: str
    expected_output: float


class ScenarioPayload(BaseModel):
    schedule: list[ScheduleEntry]


@router.get("/current")
def shortfall_current(zone_id: str | None = Query(None)) -> dict:
    """Current schedule's shortfall + risk (mine-level or per-zone)."""
    return get_current_shortfall(zone_id=zone_id)


@router.post("/scenario")
def shortfall_scenario(
    payload: ScenarioPayload,
    zone_id: str | None = Query(None),
    _: None = Depends(require_api_key),
) -> dict:
    """Shortfall + risk for a hypothetical schedule (Phase 18+ optimizer)."""
    entries = [
        {
            "date": e.date,
            "shift": e.shift,
            "equipment_id": e.equipment_id,
            "zone_id": e.zone_id,
            "expected_output": e.expected_output,
        }
        for e in payload.schedule
    ]
    return get_scenario_shortfall(entries, zone_id=zone_id)
