from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Production(Base, TimestampMixin):
    """Daily production records per mine and optionally per zone."""

    __tablename__ = "production"
    __table_args__ = (
        Index("uq_production_date_zone_id", "date", "zone_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mine_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    zone_id: Mapped[str | None] = mapped_column(String(16), ForeignKey("zones.zone_id"), index=True)
    planned_production: Mapped[float | None] = mapped_column(Float)
    actual_production: Mapped[float | None] = mapped_column(Float)
    ore_grade: Mapped[float | None] = mapped_column(Float)
