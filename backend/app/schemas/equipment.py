from datetime import datetime

from app.schemas.common import CreateSchema, ReadSchema


class EquipmentCreate(CreateSchema):
    equipment_id: str
    mine_id: str
    equipment_type: str | None = None
    current_zone_id: str | None = None
    availability: float | None = None
    operating_hours: float | None = None
    downtime_hours: float | None = None
    maintenance_hours: float | None = None
    capacity: float | None = None


class EquipmentRead(ReadSchema):
    equipment_id: str
    mine_id: str
    equipment_type: str | None
    current_zone_id: str | None
    availability: float | None
    operating_hours: float | None
    downtime_hours: float | None
    maintenance_hours: float | None
    capacity: float | None
    created_at: datetime
    updated_at: datetime
