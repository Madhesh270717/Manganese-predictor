from datetime import date, datetime

from app.schemas.common import CreateSchema, ReadSchema


class WeatherCreate(CreateSchema):
    zone_id: str
    date: date
    latitude: float | None = None
    longitude: float | None = None
    location: str | None = None  # WKT point
    rainfall_1d: float | None = None
    rainfall_7d: float | None = None
    rainfall_30d: float | None = None


class WeatherRead(ReadSchema):
    id: int
    zone_id: str
    date: date
    latitude: float | None
    longitude: float | None
    location: str | None
    rainfall_1d: float | None
    rainfall_7d: float | None
    rainfall_30d: float | None
    created_at: datetime
    updated_at: datetime
