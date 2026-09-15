"""Tests for the data confidence service (summary/detail payloads)."""

from datetime import datetime, timezone

from app.core.seed_data_sources import DATA_SOURCE_REGISTRY
from app.models.enums import ConfidenceLevel, SourceType
from app.services.data_confidence import get_confidence, get_data_confidence_summary


class FakeRow:
    def __init__(self, entry):
        self.dataset_name = entry["dataset_name"]
        self.source_type = SourceType(entry["source_type"])
        self.confidence_level = ConfidenceLevel(entry["confidence_level"])
        self.source_name = entry["source_name"]
        self.last_updated = datetime(2026, 8, 27, tzinfo=timezone.utc)


class ScalarResultStub:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self):
        self.rows = [FakeRow(e) for e in DATA_SOURCE_REGISTRY]

    def scalar(self, stmt):
        dataset = stmt._where_criteria[0].right.value
        return next((r for r in self.rows if r.dataset_name == dataset), None)

    def scalars(self, stmt):
        return ScalarResultStub(self.rows)


def test_get_confidence_returns_structured_object():
    session = FakeSession()
    result = get_confidence(session, "Geological")
    assert result == {
        "dataset": "Geological",
        "source_type": "synthetic",
        "confidence_level": "SYNTHETIC",
        "source_name": "synthetic-generated (GSI/BhuKosh inaccessible: login-gated)",
        "last_updated": "2026-08-27T00:00:00+00:00",
    }


def test_get_confidence_aliases_exploration():
    session = FakeSession()
    result = get_confidence(session, "Drilling")
    assert result["dataset"] == "Exploration/Drilling"
    assert result["confidence_level"] == "MEDIUM"


def test_get_confidence_unknown_returns_none():
    session = FakeSession()
    assert get_confidence(session, "Unknown") is None


def test_summary_matches_prd_layout():
    session = FakeSession()
    payload = get_data_confidence_summary(session)
    assert set(payload["summary"]) == {
        "Geological",
        "Satellite",
        "Weather",
        "Production",
        "Equipment",
        "Blasting",
        "Geochemical",
        "Exploration/Drilling",
        "MiningSchedule",
    }
    assert payload["summary"]["Geological"] == "SYNTHETIC"
    assert payload["summary"]["Production"] == "MEDIUM"
    assert payload["summary"]["Equipment"] == "SYNTHETIC"
    assert payload["summary"]["Blasting"] == "SYNTHETIC"
    assert len(payload["datasets"]) == 9
    first = payload["datasets"][0]
    assert set(first) == {"dataset", "source_type", "confidence_level", "source_name", "last_updated"}
