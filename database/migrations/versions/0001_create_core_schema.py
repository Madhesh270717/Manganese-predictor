"""create core schema: zones + 9 datasets + data source metadata

Revision ID: 0001
Revises:
Create Date: 2026-08-27

"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostGIS extension (also enabled by database/init.sql for fresh containers).
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # NOTE: the enums used below (confidence_level, schedule_status, source_type)
    # are created inline by op.create_table when the first table using each type
    # is created.

    op.create_table(
        "zones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.String(length=16), nullable=False),
        sa.Column("mine_id", sa.String(length=64), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("row_label", sa.String(length=8), nullable=True),
        sa.Column("col_label", sa.String(length=8), nullable=True),
        sa.Column("area_sq_m", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_zones")),
        sa.UniqueConstraint("zone_id", name=op.f("uq_zones_zone_id")),
    )
    op.create_index(op.f("ix_zones_mine_id"), "zones", ["mine_id"], unique=False)
    op.create_index(op.f("ix_zones_zone_id"), "zones", ["zone_id"], unique=False)
    op.create_index("ix_zones_geometry_gist", "zones", ["geometry"], unique=False, postgresql_using="gist")

    op.create_table(
        "geological",
        sa.Column("location_id", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=16), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("lithology", sa.String(length=128), nullable=True),
        sa.Column("geological_unit", sa.String(length=128), nullable=True),
        sa.Column("fault_distance", sa.Float(), nullable=True),
        sa.Column("lineament_distance", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], name=op.f("fk_geological_zone_id_zones")),
        sa.PrimaryKeyConstraint("location_id", name=op.f("pk_geological")),
    )
    op.create_index(op.f("ix_geological_zone_id"), "geological", ["zone_id"], unique=False)
    op.create_index("ix_geological_location_gist", "geological", ["location"], unique=False, postgresql_using="gist")

    op.create_table(
        "geochemical",
        sa.Column("location_id", sa.String(length=64), nullable=False),
        sa.Column("mn_concentration", sa.Float(), nullable=True),
        sa.Column("fe_concentration", sa.Float(), nullable=True),
        sa.Column("sio2", sa.Float(), nullable=True),
        sa.Column("other_elements", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["geological.location_id"], name=op.f("fk_geochemical_location_id_geological")),
        sa.PrimaryKeyConstraint("location_id", name=op.f("pk_geochemical")),
    )

    op.create_table(
        "exploration",
        sa.Column("drill_id", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=16), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("depth", sa.Float(), nullable=True),
        sa.Column("ore_thickness", sa.Float(), nullable=True),
        sa.Column("mn_grade", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], name=op.f("fk_exploration_zone_id_zones")),
        sa.PrimaryKeyConstraint("drill_id", name=op.f("pk_exploration")),
    )
    op.create_index(op.f("ix_exploration_zone_id"), "exploration", ["zone_id"], unique=False)
    op.create_index("ix_exploration_location_gist", "exploration", ["location"], unique=False, postgresql_using="gist")

    op.create_table(
        "satellite",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.String(length=16), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("ndvi", sa.Float(), nullable=True),
        sa.Column("lst", sa.Float(), nullable=True),
        sa.Column("soil_moisture", sa.Float(), nullable=True),
        sa.Column("spectral_features", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], name=op.f("fk_satellite_zone_id_zones")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_satellite")),
    )
    op.create_index(op.f("ix_satellite_date"), "satellite", ["date"], unique=False)
    op.create_index(op.f("ix_satellite_zone_id"), "satellite", ["zone_id"], unique=False)
    op.create_index("ix_satellite_location_gist", "satellite", ["location"], unique=False, postgresql_using="gist")

    op.create_table(
        "weather",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.String(length=16), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("rainfall_1d", sa.Float(), nullable=True),
        sa.Column("rainfall_7d", sa.Float(), nullable=True),
        sa.Column("rainfall_30d", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], name=op.f("fk_weather_zone_id_zones")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weather")),
    )
    op.create_index(op.f("ix_weather_date"), "weather", ["date"], unique=False)
    op.create_index(op.f("ix_weather_zone_id"), "weather", ["zone_id"], unique=False)
    op.create_index("ix_weather_location_gist", "weather", ["location"], unique=False, postgresql_using="gist")

    op.create_table(
        "production",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("mine_id", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=16), nullable=True),
        sa.Column("planned_production", sa.Float(), nullable=True),
        sa.Column("actual_production", sa.Float(), nullable=True),
        sa.Column("ore_grade", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], name=op.f("fk_production_zone_id_zones")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_production")),
    )
    op.create_index(op.f("ix_production_date"), "production", ["date"], unique=False)
    op.create_index(op.f("ix_production_mine_id"), "production", ["mine_id"], unique=False)
    op.create_index(op.f("ix_production_zone_id"), "production", ["zone_id"], unique=False)

    op.create_table(
        "equipment",
        sa.Column("equipment_id", sa.String(length=64), nullable=False),
        sa.Column("mine_id", sa.String(length=64), nullable=False),
        sa.Column("equipment_type", sa.String(length=64), nullable=True),
        sa.Column("current_zone_id", sa.String(length=16), nullable=True),
        sa.Column("availability", sa.Float(), nullable=True),
        sa.Column("operating_hours", sa.Float(), nullable=True),
        sa.Column("downtime_hours", sa.Float(), nullable=True),
        sa.Column("maintenance_hours", sa.Float(), nullable=True),
        sa.Column("capacity", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["current_zone_id"], ["zones.zone_id"], name=op.f("fk_equipment_current_zone_id_zones")),
        sa.PrimaryKeyConstraint("equipment_id", name=op.f("pk_equipment")),
    )
    op.create_index(op.f("ix_equipment_current_zone_id"), "equipment", ["current_zone_id"], unique=False)
    op.create_index(op.f("ix_equipment_mine_id"), "equipment", ["mine_id"], unique=False)

    op.create_table(
        "blasting",
        sa.Column("blast_id", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=16), nullable=False),
        sa.Column("planned_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delay_hours", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], name=op.f("fk_blasting_zone_id_zones")),
        sa.PrimaryKeyConstraint("blast_id", name=op.f("pk_blasting")),
    )
    op.create_index(op.f("ix_blasting_zone_id"), "blasting", ["zone_id"], unique=False)

    op.create_table(
        "mining_schedule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("shift", sa.String(length=16), nullable=True),
        sa.Column("equipment_id", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=16), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=True),
        sa.Column("planned_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_output", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("proposed", "accepted", "active", "completed", name="schedule_status"),
            nullable=False,
            server_default="proposed",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.equipment_id"], name=op.f("fk_mining_schedule_equipment_id_equipment")),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.zone_id"], name=op.f("fk_mining_schedule_zone_id_zones")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mining_schedule")),
    )
    op.create_index(op.f("ix_mining_schedule_date"), "mining_schedule", ["date"], unique=False)
    op.create_index(op.f("ix_mining_schedule_equipment_id"), "mining_schedule", ["equipment_id"], unique=False)
    op.create_index(op.f("ix_mining_schedule_zone_id"), "mining_schedule", ["zone_id"], unique=False)

    op.create_table(
        "data_source_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_name", sa.String(length=64), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("real", "synthetic", name="source_type"),
            nullable=False,
        ),
        sa.Column(
            "confidence_level",
            sa.Enum("HIGH", "MEDIUM", "LOW", "SYNTHETIC", name="confidence_level"),
            nullable=False,
        ),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_source_metadata")),
        sa.UniqueConstraint("dataset_name", name=op.f("uq_data_source_metadata_dataset_name")),
    )
    op.create_index(op.f("ix_data_source_metadata_dataset_name"), "data_source_metadata", ["dataset_name"], unique=False)


def downgrade() -> None:
    op.drop_table("data_source_metadata")
    op.drop_table("mining_schedule")
    op.drop_table("blasting")
    op.drop_table("equipment")
    op.drop_table("production")
    op.drop_table("weather")
    op.drop_table("satellite")
    op.drop_table("exploration")
    op.drop_table("geochemical")
    op.drop_table("geological")
    op.drop_table("zones")

    sa.Enum("proposed", "accepted", "active", "completed", name="schedule_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum("real", "synthetic", name="source_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum("HIGH", "MEDIUM", "LOW", "SYNTHETIC", name="confidence_level").drop(op.get_bind(), checkfirst=True)
