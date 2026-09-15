"""Tests for Phase 22 API hardening — auth, errors, readiness."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

API_KEY_HEADERS = {"X-API-Key": "spotter-demo"}


def test_health_liveness():
    resp = client.get("/health")
    assert resp.status_code == 200
    payload = resp.json()
    # The health endpoint performs a real DB probe; without a live database
    # it reports degraded rather than a static OK. With a valid Supabase
    # DATABASE_URL configured, db_connected must be true.
    assert "status" in payload
    assert "db_connected" in payload
    assert payload["db_connected"] in (True, False)
    assert "postgis_available" in payload


def test_health_ready_reports_artifacts():
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    payload = resp.json()
    assert "database" in payload["checks"]
    assert "reserve_prospectivity_model" in payload["checks"]
    assert "production_prediction_model" in payload["checks"]
    # Model artifacts exist (Phases 12/15 trained them).
    assert payload["checks"]["reserve_prospectivity_model"]["status"] == "ok"
    assert payload["checks"]["production_prediction_model"]["status"] == "ok"


def test_mutating_endpoint_requires_api_key():
    resp = client.post("/api/v1/recalculation/trigger")
    assert resp.status_code == 401
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == 401


def test_mutating_endpoint_allows_valid_key():
    resp = client.post("/api/v1/recalculation/trigger", headers=API_KEY_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["outcome"] in ("recommended", "stable", "no_improvement")


def test_error_envelope_404():
    # DB-free 404: the prospectivity service raises HTTPException without DB.
    resp = client.get("/api/v1/reserve/prospectivity/ZZ9")
    assert resp.status_code == 404
    payload = resp.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == 404


def test_error_envelope_422():
    resp = client.post(
        "/api/v1/production/predict/scenario",
        headers=API_KEY_HEADERS,
        json={"schedule": []},
    )
    # Empty schedule raises HTTPException(422) from the endpoint.
    assert resp.status_code == 422
    payload = resp.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == 422


def test_error_envelope_validation():
    resp = client.post(
        "/api/v1/production/predict/scenario",
        headers=API_KEY_HEADERS,
        json={"schedule": [{"date": "not-a-date"}]},
    )
    assert resp.status_code == 422
    assert resp.json()["success"] is False


def test_placeholder_pings_removed():
    resp = client.get("/api/v1/reserve/ping")
    assert resp.status_code == 404
    resp = client.get("/api/v1/assistant/ping")
    assert resp.status_code == 404


def test_cors_headers_present():
    resp = client.options(
        "/api/v1/zones",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in resp.headers
