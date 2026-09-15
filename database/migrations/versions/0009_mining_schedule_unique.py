"""add unique constraint on mining_schedule (date, shift, equipment_id)

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-28

The Phase 10 seed upserts MINING_SCHEDULE with
ON CONFLICT (date, shift, equipment_id); the unique index this requires
was missing from migration 0001, so idempotent re-seeding failed against a
real PostgreSQL (Supabase). Adds the constraint the upsert targets.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dedupe first (in case prior seeds left duplicates on a live DB).
    op.execute(
        """
        DELETE FROM mining_schedule a USING mining_schedule b
        WHERE a.id > b.id
          AND a.date = b.date
          AND a.shift = b.shift
          AND a.equipment_id = b.equipment_id
        """
    )
    op.create_index(
        "uq_mining_schedule_date_shift_equipment",
        "mining_schedule",
        ["date", "shift", "equipment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_mining_schedule_date_shift_equipment", table_name="mining_schedule")
