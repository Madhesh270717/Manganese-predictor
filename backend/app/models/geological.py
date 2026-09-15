from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Geological(Base, TimestampMixin):
    """Geological survey observations per zone."""

    __tablename__ = "geological"
    __table_args__ = (
        Index("ix_geological_location_gist", "location", postgresql_using="gist"),
    )

    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    zone_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("zones.zone_id"), nullable=False, index=True
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location: Mapped[Any] = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=False))
    lithology: Mapped[str | None] = mapped_column(String(128))
    geological_unit: Mapped[str | None] = mapped_column(String(128))
    fault_distance: Mapped[float | None] = mapped_column(Float)
    lineament_distance: Mapped[float | None] = mapped_column(Float)
