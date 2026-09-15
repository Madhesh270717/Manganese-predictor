from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Equipment(Base, TimestampMixin):
    """Mining equipment master data and current status."""

    __tablename__ = "equipment"

    equipment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mine_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    equipment_type: Mapped[str | None] = mapped_column(String(64))
    current_zone_id: Mapped[str | None] = mapped_column(
        String(16), ForeignKey("zones.zone_id"), index=True
    )
    availability: Mapped[float | None] = mapped_column(Float)
    operating_hours: Mapped[float | None] = mapped_column(Float)
    downtime_hours: Mapped[float | None] = mapped_column(Float)
    maintenance_hours: Mapped[float | None] = mapped_column(Float)
    capacity: Mapped[float | None] = mapped_column(Float)
