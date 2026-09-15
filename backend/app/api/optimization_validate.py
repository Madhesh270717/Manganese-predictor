"""Optimization validation API — Phase 18 (debugging; Phase 19–20 reuse)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import require_api_key
from ml.pipelines.optimization.schedule_model import CandidateSchedule
from ml.pipelines.optimization.validator import validate_schedule
from ml.pipelines.optimization.or_tools_model import build_and_solve

router = APIRouter(prefix="/optimization", tags=["optimization-foundation"])


class ScheduleEntryModel(BaseModel):
    date: date
    shift: str = Field(pattern="^[A-B]$")
    equipment_id: str
    zone_id: str
    operation: str = "excavation"
    expected_output: float


class ValidatePayload(BaseModel):
    schedule: list[ScheduleEntryModel]


@router.post("/validate-schedule")
def validate_schedule_endpoint(
    payload: ValidatePayload, _: None = Depends(require_api_key)
) -> dict:
    """Validate a candidate schedule against the PRD §22 constraints.

    Requires X-API-Key (mutating/intensive compute).
    """
    if not payload.schedule:
        raise HTTPException(status_code=422, detail="schedule must not be empty")

    schedule = CandidateSchedule.from_dicts([e.model_dump() for e in payload.schedule])
    report = validate_schedule(schedule)

    cp_result = build_and_solve(schedule)

    return {
        **report,
        "or_tools": {
            "status": cp_result["status"],
            "feasible": cp_result["feasible"],
        },
    }
