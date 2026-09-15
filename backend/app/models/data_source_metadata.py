from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import ConfidenceLevel, SourceType


def _enum_values(enum_cls):
    """Use the enum member VALUES (lowercase) for the DB enum.

    The migration 0001 created source_type with values ('real','synthetic');
    without this callable SQLAlchemy would send the member NAMES
    ('REAL','SYNTHETIC'), which PostgreSQL rejects.
    """
    return [member.value for member in enum_cls]


class DataSourceMetadata(Base, TimestampMixin):
    """Registry of dataset provenance backing the Data Confidence indicator (PRD Section 39)."""

    __tablename__ = "data_source_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", native_enum=True, values_callable=_enum_values),
        nullable=False,
    )
    confidence_level: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel, name="confidence_level", native_enum=True, values_callable=_enum_values),
        nullable=False,
    )
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
