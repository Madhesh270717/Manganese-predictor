from datetime import datetime

from app.schemas.common import CreateSchema, ReadSchema


class BlastingCreate(CreateSchema):
    blast_id: str
    zone_id: str
    planned_time: datetime | None = None
    actual_time: datetime | None = None
    delay_hours: float | None = None


class BlastingRead(ReadSchema):
    blast_id: str
    zone_id: str
    planned_time: datetime | None
    actual_time: datetime | None
    delay_hours: float | None
    created_at: datetime
    updated_at: datetime
