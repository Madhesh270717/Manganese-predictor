from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.data_source_metadata import _enum_values
from app.models.enums import ScheduleStatus


class MiningSchedule(Base, TimestampMixin):
    """Dynamic mine scheduling entries per date/shift."""

    __tablename__ = "mining_schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift: Mapped[str | None] = mapped_column(String(16))
    equipment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("equipment.equipment_id"), nullable=False, index=True
    )
    zone_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("zones.zone_id"), nullable=False, index=True
    )
    operation: Mapped[str | None] = mapped_column(String(64))
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_output: Mapped[float | None] = mapped_column(Float)
    status: Mapped[ScheduleStatus] = mapped_column(
        Enum(ScheduleStatus, name="schedule_status", native_enum=True, values_callable=_enum_values),
        nullable=False,
        default=ScheduleStatus.PROPOSED,
        server_default=ScheduleStatus.PROPOSED.value,
    )
