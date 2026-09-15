from datetime import date
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Weather(Base, TimestampMixin):
    """Weather observations per zone and date."""

    __tablename__ = "weather"
    __table_args__ = (
        Index("ix_weather_location_gist", "location", postgresql_using="gist"),
        Index("uq_weather_zone_id_date", "zone_id", "date", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("zones.zone_id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location: Mapped[Any] = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=False))
    rainfall_1d: Mapped[float | None] = mapped_column(Float)
    rainfall_7d: Mapped[float | None] = mapped_column(Float)
    rainfall_30d: Mapped[float | None] = mapped_column(Float)
    scenario: Mapped[str] = mapped_column(String(16), nullable=False, default="historical", server_default="historical")
