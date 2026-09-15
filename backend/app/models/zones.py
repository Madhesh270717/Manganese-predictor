from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Zone(Base, TimestampMixin):
    """Foundational spatial grid/zone cell — every dataset table references this."""

    __tablename__ = "zones"
    __table_args__ = (
        Index("ix_zones_geometry_gist", "geometry", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    mine_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    geometry: Mapped[Any] = mapped_column(
        Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False), nullable=False
    )
    row_label: Mapped[str | None] = mapped_column(String(8))
    col_label: Mapped[str | None] = mapped_column(String(8))
    area_sq_m: Mapped[float | None] = mapped_column(Float)
