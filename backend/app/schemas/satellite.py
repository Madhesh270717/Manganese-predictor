from datetime import date, datetime
from typing import Any

from app.schemas.common import CreateSchema, ReadSchema


class SatelliteCreate(CreateSchema):
    zone_id: str
    latitude: float | None = None
    longitude: float | None = None
    location: str | None = None  # WKT point
    date: date
    ndvi: float | None = None
    lst: float | None = None
    soil_moisture: float | None = None
    spectral_features: dict[str, Any] | None = None


class SatelliteRead(ReadSchema):
    id: int
    zone_id: str
    latitude: float | None
    longitude: float | None
    location: str | None
    date: date
    ndvi: float | None
    lst: float | None
    soil_moisture: float | None
    spectral_features: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
