from datetime import date, datetime

from app.models.enums import ScheduleStatus
from app.schemas.common import CreateSchema, ReadSchema


class MiningScheduleCreate(CreateSchema):
    date: date
    shift: str | None = None
    equipment_id: str
    zone_id: str
    operation: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    expected_output: float | None = None
    status: ScheduleStatus = ScheduleStatus.PROPOSED


class MiningScheduleRead(ReadSchema):
    id: int
    date: date
    shift: str | None
    equipment_id: str
    zone_id: str
    operation: str | None
    planned_start: datetime | None
    planned_end: datetime | None
    expected_output: float | None
    status: ScheduleStatus
    created_at: datetime
    updated_at: datetime
