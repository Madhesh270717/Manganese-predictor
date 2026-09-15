"""Zone terrain & access data — Phase 14 (Module 2 input).

Stored as a separate table rather than extra ZONE columns: terrain/access
is operational metadata refreshed independently from the spatial grid, and
keeping ZONE lean keeps the grid reads (map rendering) fast.
"""

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ZoneTerrainAccess(Base, TimestampMixin):
    __tablename__ = "zone_terrain_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zone_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("zones.zone_id"), unique=True, nullable=False, index=True
    )
    slope_degrees: Mapped[float | None] = mapped_column(Float)
    accessibility_rating: Mapped[str | None] = mapped_column(String(16))  # GOOD/MODERATE/POOR
    haul_distance_km: Mapped[float | None] = mapped_column(Float)
    road_condition: Mapped[str | None] = mapped_column(String(16))  # GOOD/MODERATE/POOR
