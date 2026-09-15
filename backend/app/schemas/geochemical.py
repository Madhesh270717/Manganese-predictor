from datetime import datetime
from typing import Any

from app.schemas.common import CreateSchema, ReadSchema


class GeochemicalCreate(CreateSchema):
    location_id: str
    mn_concentration: float | None = None
    fe_concentration: float | None = None
    sio2: float | None = None
    other_elements: dict[str, Any] | None = None


class GeochemicalRead(ReadSchema):
    location_id: str
    mn_concentration: float | None
    fe_concentration: float | None
    sio2: float | None
    other_elements: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
