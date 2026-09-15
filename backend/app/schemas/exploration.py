from datetime import datetime

from app.schemas.common import CreateSchema, ReadSchema


class ExplorationCreate(CreateSchema):
    drill_id: str
    zone_id: str
    latitude: float | None = None
    longitude: float | None = None
    location: str | None = None  # WKT point
    depth: float | None = None
    ore_thickness: float | None = None
    mn_grade: float | None = None


class ExplorationRead(ReadSchema):
    drill_id: str
    zone_id: str
    latitude: float | None
    longitude: float | None
    location: str | None
    depth: float | None
    ore_thickness: float | None
    mn_grade: float | None
    created_at: datetime
    updated_at: datetime
