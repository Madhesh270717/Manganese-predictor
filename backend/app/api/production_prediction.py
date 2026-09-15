"""Production Prediction API — Phase 15 (PRD Sections 12–16)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import require_api_key
from app.services.production_prediction_service import (
    predict_current,
    predict_production,
)

router = APIRouter(prefix="/production/predict", tags=["production-prediction"])


class ScheduleEntry(BaseModel):
    date: date
    shift: str = Field(default="A", pattern="^[A-B]$")
    equipment_id: str
    zone_id: str
    expected_output: float


class ScenarioPayload(BaseModel):
    schedule: list[ScheduleEntry]


@router.get("/current")
def predict_current_endpoint() -> dict:
    """Predict production for the current active schedule (the 'before' state)."""
    return predict_current()


@router.post("/scenario")
def predict_scenario(payload: ScenarioPayload, _: None = Depends(require_api_key)) -> dict:
    """Predict production for a hypothetical schedule (Phase 18+ optimizer).

    Requires X-API-Key (mutating/intensive compute).
    """
    if not payload.schedule:
        raise HTTPException(status_code=422, detail="schedule must not be empty")
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
    return predict_production(entries)
