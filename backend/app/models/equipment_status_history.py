"""Equipment status history — per-unit daily availability time series (Phase 9).

Stored separately from EQUIPMENT (current snapshot) — documented schema
decision: the fleet table keeps the latest state for scheduling lookups,
while this table holds the 90-day history the Production model (Phase 15)
trains against.
"""

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class EquipmentStatusHistory(Base, TimestampMixin):
    __tablename__ = "equipment_status_history"
    __table_args__ = (
        Index("uq_equip_hist_equipment_date", "equipment_id", "date", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("equipment.equipment_id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    availability: Mapped[float | None] = mapped_column(Float)
    operating_hours: Mapped[float | None] = mapped_column(Float)
    downtime_hours: Mapped[float | None] = mapped_column(Float)
    maintenance_hours: Mapped[float | None] = mapped_column(Float)
