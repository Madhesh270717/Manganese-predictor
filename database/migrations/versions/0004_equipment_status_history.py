"""add equipment_status_history table

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-27

Phase 9: per-unit daily equipment status time series for the Production
model (Phase 15). The EQUIPMENT table keeps the current snapshot.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "equipment_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.String(length=64), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("availability", sa.Float(), nullable=True),
        sa.Column("operating_hours", sa.Float(), nullable=True),
        sa.Column("downtime_hours", sa.Float(), nullable=True),
        sa.Column("maintenance_hours", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["equipment_id"], ["equipment.equipment_id"],
            name=op.f("fk_equipment_status_history_equipment_id_equipment"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_equipment_status_history")),
    )
    op.create_index(
        "uq_equip_hist_equipment_date",
        "equipment_status_history",
        ["equipment_id", "date"],
        unique=True,
    )
    op.create_index(
        op.f("ix_equipment_status_history_equipment_id"),
        "equipment_status_history",
        ["equipment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_equipment_status_history_date"),
        "equipment_status_history",
        ["date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_equipment_status_history_date"), table_name="equipment_status_history")
    op.drop_index(op.f("ix_equipment_status_history_equipment_id"), table_name="equipment_status_history")
    op.drop_index("uq_equip_hist_equipment_date", table_name="equipment_status_history")
    op.drop_table("equipment_status_history")
