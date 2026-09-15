"""Recalculation log — Phase 21 (PRD Section 24 audit trail).

Records every recalculation cycle: when/why it ran, before/after
shortfall, and the outcome. Consumed by the AI Assistant (Phase 29) for
"when was this recommendation generated and why" questions.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RecalculationLog(Base, TimestampMixin):
    __tablename__ = "recalculation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trigger_reason: Mapped[str] = mapped_column(String(128))
    previous_shortfall: Mapped[float | None] = mapped_column(Float)
    new_shortfall: Mapped[float | None] = mapped_column(Float)
    recommendation_id: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(32))  # stable/recommended/no_improvement
    detail: Mapped[str | None] = mapped_column(Text)
