from datetime import datetime

from app.schemas.common import CreateSchema, ReadSchema


class ZoneCreate(CreateSchema):
    zone_id: str
    mine_id: str
    geometry: str  # WKT polygon
    row_label: str | None = None
    col_label: str | None = None
    area_sq_m: float | None = None


class ZoneRead(ReadSchema):
    id: int
    zone_id: str
    mine_id: str
    geometry: str
    row_label: str | None
    col_label: str | None
    area_sq_m: float | None
    created_at: datetime
    updated_at: datetime
