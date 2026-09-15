"""Tests for the data source registry seed (PRD Section 39)."""

from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql

from app.core.seed_data_sources import DATA_SOURCE_REGISTRY, build_seed_statement
from app.models.enums import ConfidenceLevel, SourceType

EXPECTED_CONFIDENCE = {
    "Geological": ConfidenceLevel.SYNTHETIC,
    "Satellite": ConfidenceLevel.HIGH,
    "Weather": ConfidenceLevel.HIGH,
    "Production": ConfidenceLevel.MEDIUM,
    "Equipment": ConfidenceLevel.SYNTHETIC,
    "Blasting": ConfidenceLevel.SYNTHETIC,
    "Geochemical": ConfidenceLevel.SYNTHETIC,
    "Exploration/Drilling": ConfidenceLevel.MEDIUM,
    "MiningSchedule": ConfidenceLevel.SYNTHETIC,
}

EXPECTED_SOURCE_TYPE = {
    "Geological": SourceType.SYNTHETIC,
    "Satellite": SourceType.REAL,
    "Weather": SourceType.REAL,
    "Production": SourceType.SYNTHETIC,
    "Equipment": SourceType.SYNTHETIC,
    "Blasting": SourceType.SYNTHETIC,
    "Geochemical": SourceType.SYNTHETIC,
    "Exploration/Drilling": SourceType.SYNTHETIC,
    "MiningSchedule": SourceType.SYNTHETIC,
}

EXPECTED_SOURCE_NAME = {
    "Geological": "synthetic-generated (GSI/BhuKosh inaccessible: login-gated)",
    "Satellite": "ISRO/Bhuvan, Sentinel, Landsat",
    "Weather": "IMD, NASA GPM",
    "Production": "synthetic-generated (MOIL zone-level data unavailable)",
    "Equipment": "synthetic-generated",
    "Blasting": "synthetic-generated",
    "Geochemical": "synthetic-generated (GSI/NGDR inaccessible: login-gated)",
    "Exploration/Drilling": "synthetic-generated (GSI/NGDR inaccessible: login-gated)",
    "MiningSchedule": "synthetic-generated (operational/internal data)",
}


def test_registry_has_exactly_9_rows():
    assert len(DATA_SOURCE_REGISTRY) == 9


def test_registry_matches_prd_section_39():
    by_name = {row["dataset_name"]: row for row in DATA_SOURCE_REGISTRY}
    assert set(by_name) == set(EXPECTED_CONFIDENCE)

    for name, confidence in EXPECTED_CONFIDENCE.items():
        assert by_name[name]["confidence_level"] == confidence.value, name

    for name, source_type in EXPECTED_SOURCE_TYPE.items():
        assert by_name[name]["source_type"] == source_type.value, name

    for name, source in EXPECTED_SOURCE_NAME.items():
        assert by_name[name]["source_name"] == source, name


def test_seed_statement_compiles():
    now = datetime(2026, 8, 27, tzinfo=timezone.utc)
    sql = str(
        build_seed_statement(now).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "ON CONFLICT" in sql.upper()
    assert "data_source_metadata" in sql
    assert "synthetic-generated" in sql
