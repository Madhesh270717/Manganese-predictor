"""add scenario column + unique index to weather

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-27

Phase 8 weather seeding needs:
- scenario flag to distinguish historical baseline vs demo trigger rows
- unique (zone_id, date) for idempotent upserts
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "weather",
        sa.Column("scenario", sa.String(length=16), nullable=False, server_default="historical"),
    )
    op.create_index(
        "uq_weather_zone_id_date",
        "weather",
        ["zone_id", "date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_weather_zone_id_date", table_name="weather")
    op.drop_column("weather", "scenario")
