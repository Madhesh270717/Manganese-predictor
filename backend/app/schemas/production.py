from datetime import date, datetime

from app.schemas.common import CreateSchema, ReadSchema


class ProductionCreate(CreateSchema):
    date: date
    mine_id: str
    zone_id: str | None = None
    planned_production: float | None = None
    actual_production: float | None = None
    ore_grade: float | None = None


class ProductionRead(ReadSchema):
    id: int
    date: date
    mine_id: str
    zone_id: str | None
    planned_production: float | None
    actual_production: float | None
    ore_grade: float | None
    created_at: datetime
    updated_at: datetime
