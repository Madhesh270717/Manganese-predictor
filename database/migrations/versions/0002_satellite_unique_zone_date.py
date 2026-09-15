"""add unique index on satellite (zone_id, date)

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-27

The Phase 7 satellite seeding upserts on (zone_id, date), so the pair must
be unique.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_satellite_zone_id_date",
        "satellite",
        ["zone_id", "date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_satellite_zone_id_date", table_name="satellite")
