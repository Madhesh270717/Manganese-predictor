"""Non-functional requirements verification — Phase 30 (PRD Section 41).

Explicit checks (not assumed):
  * Security    — mutating POST endpoints reject missing/wrong API keys.
  * Reliability — DB-less demo machines get graceful synthetic fallbacks
                  (no 500s) from every frontend-facing endpoint.
  * Performance — dashboard endpoints respond within a few seconds on a
                  cold process (model lazy-load included).
  * Data quality — confidence/metadata fields surface in responses.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Every endpoint the 7 screens + metrics view call, in one sweep.
FRONTEND_ENDPOINTS = [
    "/api/v1/zones",
    "/api/v1/reserve/prospectivity",
    "/api/v1/reserve/resource-estimate",
    "/api/v1/reserve/resource-estimate/B3",
    "/api/v1/reserve/prospectivity/B3",
    "/api/v1/mineability",
    "/api/v1/mineability/B3",
    "/api/v1/production/history",
    "/api/v1/production/current-target",
    "/api/v1/production/predict/current",
    "/api/v1/production/shortfall/current",
    "/api/v1/production/shortfall/current/explain",
    "/api/v1/optimization/risks",
    "/api/v1/optimization/alternatives/EX-04",
    "/api/v1/weather/risk-alert",
    "/api/v1/schedule/current",
    "/api/v1/equipment",
    "/api/v1/equipment/EX-04",
    "/api/v1/equipment/by-zone/A1",
    "/api/v1/recommendations",
    "/api/v1/recommendations/EX-04",
    "/api/v1/recommendations/EX-04/schedule-comparison",
    "/api/v1/data-confidence",
    "/api/v1/demo/state",
    "/api/v1/metrics/summary",
    "/api/v1/zones/B3/drilling",
    "/api/v1/zones/B3/geological",
    "/api/v1/zones/A1/weather",
    "/api/v1/zones/A1/weather/current",
    "/api/v1/zones/B3/satellite",
    "/api/v1/zones/B3/satellite/latest",
    "/api/v1/equipment/EX-04/history",
]


@pytest.mark.parametrize("path", FRONTEND_ENDPOINTS)
def test_all_frontend_endpoints_reachable_without_db(path):
    """Reliability (PRD §41): no frontend-facing endpoint 500s on a DB-less
    machine — every one must degrade to its synthetic fallback."""
    resp = client.get(path)
    assert resp.status_code == 200, f"{path} -> {resp.status_code}: {resp.text[:200]}"


def test_unknown_zone_returns_404_not_500():
    resp = client.get("/api/v1/zones/ZZ9/drilling")
    assert resp.status_code == 404
    assert resp.json()["success"] is False


def test_unknown_equipment_returns_404_not_500():
    resp = client.get("/api/v1/equipment/XX-99")
    assert resp.status_code == 404


def test_mutating_endpoints_require_api_key():
    """Security (PRD §41): mutating POSTs are blocked without the key."""
    for path in [
        "/api/v1/demo/accept",
        "/api/v1/demo/reset",
        "/api/v1/recalculation/trigger",
        "/api/v1/optimization/validate-schedule",
    ]:
        resp = client.post(path, json={"schedule": []} if "validate" in path else {})
        assert resp.status_code == 401, f"{path} -> {resp.status_code}"
        assert resp.json()["error"]["code"] == 401


def test_mutating_endpoints_allow_valid_key():
    headers = {"X-API-Key": "spotter-demo"}
    resp = client.post("/api/v1/demo/reset", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["reset"] is True


def test_dashboard_endpoints_performant_cold():
    """Performance (PRD §41): the main dashboard endpoints complete within a
    few seconds, including cold model lazy-loads on this machine."""
    budget = 8.0  # generous CI bound; warm calls are well under 1s
    for path in [
        "/api/v1/reserve/prospectivity",
        "/api/v1/production/predict/current",
        "/api/v1/mineability",
        "/api/v1/metrics/summary",
    ]:
        start = time.monotonic()
        resp = client.get(path)
        elapsed = time.monotonic() - start
        assert resp.status_code == 200
        assert elapsed < budget, f"{path} took {elapsed:.1f}s"


def test_confidence_metadata_surfaces():
    """Data quality (PRD §41 + §39): responses carry confidence metadata."""
    resp = client.get("/api/v1/data-confidence")
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["datasets"]) > 0
    assert all("confidence_level" in d for d in payload["datasets"])

    resp = client.get("/api/v1/production/history")
    assert resp.status_code == 200
    assert "confidence" in resp.json()


def test_stale_weather_fallback_shape():
    """Reliability (PRD §41): the latest-available weather fallback returns
    a stale flag instead of failing when today's row is missing."""
    resp = client.get("/api/v1/zones/A1/weather/current")
    assert resp.status_code == 200
    payload = resp.json()
    assert "is_stale" in payload
    assert "confidence" in payload
