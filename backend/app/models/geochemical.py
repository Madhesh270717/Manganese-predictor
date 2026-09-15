from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Geochemical(Base, TimestampMixin):
    """Geochemical assay results, one row per geological sample location."""

    __tablename__ = "geochemical"

    location_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("geological.location_id"), primary_key=True
    )
    mn_concentration: Mapped[float | None] = mapped_column(Float)
    fe_concentration: Mapped[float | None] = mapped_column(Float)
    sio2: Mapped[float | None] = mapped_column(Float)
    other_elements: Mapped[dict | None] = mapped_column(JSONB)
