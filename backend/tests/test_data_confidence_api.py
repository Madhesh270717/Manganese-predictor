"""API smoke tests using dependency override (no live DB required)."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.core.seed_data_sources import DATA_SOURCE_REGISTRY
from app.main import app


@pytest.fixture(autouse=True)
def _clear_overrides():
    """Ensure the get_db override never leaks into later test modules."""
    yield
    app.dependency_overrides.clear()


class ScalarResultStub:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def scalar(self, stmt):
        dataset = stmt._where_criteria[0].right.value
        for row in self._rows:
            if row.dataset_name == dataset:
                return row
        return None

    def scalars(self, stmt):
        return ScalarResultStub(self._rows)

    def close(self):
        pass


class FakeRow:
    def __init__(self, dataset_name, source_type, confidence_level, source_name, last_updated):
        self.dataset_name = dataset_name
        self.source_type = source_type
        self.confidence_level = confidence_level
        self.source_name = source_name
        self.last_updated = last_updated


def _fake_rows():
    now = datetime(2026, 8, 27, tzinfo=timezone.utc)
    from app.models.enums import ConfidenceLevel, SourceType

    rows = []
    for entry in DATA_SOURCE_REGISTRY:
        rows.append(
            FakeRow(
                dataset_name=entry["dataset_name"],
                source_type=SourceType(entry["source_type"]),
                confidence_level=ConfidenceLevel(entry["confidence_level"]),
                source_name=entry["source_name"],
                last_updated=now,
            )
        )
    return sorted(rows, key=lambda r: r.dataset_name)


def _client():
    app.dependency_overrides[get_db] = lambda: FakeSession(_fake_rows())
    return TestClient(app)


def test_data_confidence_summary_endpoint():
    client = _client()
    resp = client.get("/api/v1/data-confidence")
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["datasets"]) == 9
    assert payload["summary"]["Geological"] == "SYNTHETIC"
    assert payload["summary"]["Equipment"] == "SYNTHETIC"
    assert payload["summary"]["Production"] == "MEDIUM"


def test_data_confidence_detail_endpoint():
    client = _client()
    resp = client.get("/api/v1/data-confidence/Equipment")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload == {
        "dataset": "Equipment",
        "source_type": "synthetic",
        "confidence_level": "SYNTHETIC",
        "source_name": "synthetic-generated",
        "last_updated": "2026-08-27T00:00:00+00:00",
    }


def test_data_confidence_unknown_dataset_404():
    client = _client()
    resp = client.get("/api/v1/data-confidence/Nope")
    assert resp.status_code == 404
