"""Explainability API — Phase 17 (PRD Section 16)."""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import require_api_key
from app.services.explainability_service import get_shortfall_contributors

router = APIRouter(prefix="/production/shortfall", tags=["production-explainability"])


class ScheduleEntry(BaseModel):
    date: date
    shift: str = Field(default="A", pattern="^[A-B]$")
    equipment_id: str
    zone_id: str
    expected_output: float


class ScenarioPayload(BaseModel):
    schedule: list[ScheduleEntry]


@router.get("/current/explain")
def explain_current() -> dict:
    """Contributor breakdown for the current schedule's shortfall."""
    return get_shortfall_contributors(schedule=None)


@router.post("/scenario/explain")
def explain_scenario(payload: ScenarioPayload, _: None = Depends(require_api_key)) -> dict:
    """Contributor breakdown for a hypothetical schedule."""
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
    return get_shortfall_contributors(schedule=entries)
