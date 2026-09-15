"""add recalculation_log table

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-27

Phase 21: audit trail for the PRD §24 recalculation loop.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recalculation_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trigger_reason", sa.String(length=128), nullable=False),
        sa.Column("previous_shortfall", sa.Float(), nullable=True),
        sa.Column("new_shortfall", sa.Float(), nullable=True),
        sa.Column("recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recalculation_log")),
    )


def downgrade() -> None:
    op.drop_table("recalculation_log")
