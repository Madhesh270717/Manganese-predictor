"""add zone_terrain_access table

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-27

Phase 14 (Mineability): terrain/access per zone — slope, accessibility,
haul distance, road condition.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zone_terrain_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.String(length=16), nullable=False),
        sa.Column("slope_degrees", sa.Float(), nullable=True),
        sa.Column("accessibility_rating", sa.String(length=16), nullable=True),
        sa.Column("haul_distance_km", sa.Float(), nullable=True),
        sa.Column("road_condition", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], name=op.f("fk_zone_terrain_access_zone_id_zones")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_zone_terrain_access")),
        sa.UniqueConstraint("zone_id", name=op.f("uq_zone_terrain_access_zone_id")),
    )
    op.create_index(
        op.f("ix_zone_terrain_access_zone_id"),
        "zone_terrain_access",
        ["zone_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_zone_terrain_access_zone_id"), table_name="zone_terrain_access")
    op.drop_table("zone_terrain_access")
