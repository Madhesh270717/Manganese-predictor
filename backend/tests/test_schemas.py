"""Schema validation smoke tests — one dummy payload per dataset via Pydantic.

Proves every Create schema validates a realistic insert payload without a
database (per acceptance criteria: "quick script inserting one dummy row per
table via the schemas should succeed").
"""

from datetime import date, datetime, timezone

import pytest

from app.schemas import (
    BlastingCreate,
    DataSourceMetadataCreate,
    EquipmentCreate,
    ExplorationCreate,
    GeochemicalCreate,
    GeologicalCreate,
    MiningScheduleCreate,
    ProductionCreate,
    SatelliteCreate,
    WeatherCreate,
    ZoneCreate,
)
from app.models.enums import ConfidenceLevel, ScheduleStatus, SourceType

POINT = "SRID=4326;POINT(21.5 82.2)"
POLYGON = "SRID=4326;POLYGON((21.0 82.0, 21.5 82.0, 21.5 82.5, 21.0 82.5, 21.0 82.0))"

ZONE_ID = "B3"
MINE_ID = "MOIL-1"


@pytest.mark.parametrize(
    "schema_cls, payload",
    [
        (
            ZoneCreate,
            {"zone_id": ZONE_ID, "mine_id": MINE_ID, "geometry": POLYGON, "row_label": "B", "col_label": "3", "area_sq_m": 25_000.0},
        ),
        (
            GeologicalCreate,
            {"location_id": "GEO-001", "zone_id": ZONE_ID, "latitude": 21.2, "longitude": 82.1, "location": POINT, "lithology": "laterite", "geological_unit": "Kodurite", "fault_distance": 150.0, "lineament_distance": 80.0},
        ),
        (
            GeochemicalCreate,
            {"location_id": "GEO-001", "mn_concentration": 42.5, "fe_concentration": 6.2, "sio2": 18.0, "other_elements": {"P": 0.12}},
        ),
        (
            ExplorationCreate,
            {"drill_id": "DR-001", "zone_id": ZONE_ID, "latitude": 21.2, "longitude": 82.1, "location": POINT, "depth": 120.0, "ore_thickness": 3.4, "mn_grade": 40.1},
        ),
        (
            SatelliteCreate,
            {"zone_id": ZONE_ID, "latitude": 21.2, "longitude": 82.1, "location": POINT, "date": date(2026, 8, 1), "ndvi": 0.62, "lst": 31.5, "soil_moisture": 0.18, "spectral_features": {"band4": 0.11}},
        ),
        (
            WeatherCreate,
            {"zone_id": ZONE_ID, "date": date(2026, 8, 1), "latitude": 21.2, "longitude": 82.1, "location": POINT, "rainfall_1d": 4.0, "rainfall_7d": 25.0, "rainfall_30d": 180.0},
        ),
        (
            ProductionCreate,
            {"date": date(2026, 8, 1), "mine_id": MINE_ID, "zone_id": ZONE_ID, "planned_production": 500.0, "actual_production": 480.0, "ore_grade": 39.5},
        ),
        (
            EquipmentCreate,
            {"equipment_id": "EXC-01", "mine_id": MINE_ID, "equipment_type": "excavator", "current_zone_id": ZONE_ID, "availability": 0.9, "operating_hours": 12.0, "downtime_hours": 1.0, "maintenance_hours": 0.5, "capacity": 60.0},
        ),
        (
            BlastingCreate,
            {"blast_id": "BL-001", "zone_id": ZONE_ID, "planned_time": datetime(2026, 8, 2, 8, 0, tzinfo=timezone.utc), "actual_time": datetime(2026, 8, 2, 8, 30, tzinfo=timezone.utc), "delay_hours": 0.5},
        ),
        (
            MiningScheduleCreate,
            {"date": date(2026, 8, 2), "shift": "A", "equipment_id": "EXC-01", "zone_id": ZONE_ID, "operation": "overburden removal", "planned_start": datetime(2026, 8, 2, 6, 0, tzinfo=timezone.utc), "planned_end": datetime(2026, 8, 2, 14, 0, tzinfo=timezone.utc), "expected_output": 450.0, "status": ScheduleStatus.PROPOSED},
        ),
        (
            DataSourceMetadataCreate,
            {"dataset_name": "Geological", "source_type": SourceType.REAL, "confidence_level": ConfidenceLevel.HIGH, "source_name": "GSI, BhuKosh", "last_updated": datetime(2026, 8, 27, tzinfo=timezone.utc)},
        ),
    ],
)
def test_create_schema_validates(schema_cls, payload):
    instance = schema_cls.model_validate(payload)
    assert instance is not None
