from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Blasting(Base, TimestampMixin):
    """Blasting operation records per zone."""

    __tablename__ = "blasting"

    blast_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    zone_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("zones.zone_id"), nullable=False, index=True
    )
    planned_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delay_hours: Mapped[float | None] = mapped_column(Float)
