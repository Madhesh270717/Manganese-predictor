from datetime import datetime

from app.schemas.common import CreateSchema, ReadSchema


class GeologicalCreate(CreateSchema):
    location_id: str
    zone_id: str
    latitude: float | None = None
    longitude: float | None = None
    location: str | None = None  # WKT point
    lithology: str | None = None
    geological_unit: str | None = None
    fault_distance: float | None = None
    lineament_distance: float | None = None


class GeologicalRead(ReadSchema):
    location_id: str
    zone_id: str
    latitude: float | None
    longitude: float | None
    location: str | None
    lithology: str | None
    geological_unit: str | None
    fault_distance: float | None
    lineament_distance: float | None
    created_at: datetime
    updated_at: datetime
