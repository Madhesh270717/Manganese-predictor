"""add unique index on production (date, zone_id)

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-27

Phase 10 seeding upserts on (date, zone_id), so the pair must be unique.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_production_date_zone_id",
        "production",
        ["date", "zone_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_production_date_zone_id", table_name="production")
