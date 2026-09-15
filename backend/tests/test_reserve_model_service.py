"""Tests for the reserve prospectivity service — Phase 12."""

import pytest

from app.services.reserve_model_service import (
    classify,
    get_all_zones_prospectivity,
    get_prospectivity,
)


def test_classify_thresholds():
    assert classify(0.1) == "LOW"
    assert classify(0.39) == "LOW"
    assert classify(0.40) == "MEDIUM"
    assert classify(0.69) == "MEDIUM"
    assert classify(0.70) == "HIGH"
    assert classify(0.99) == "HIGH"


def test_b3_scores_high_with_disclaimer():
    result = get_prospectivity("B3")
    assert result is not None
    assert result["classification"] == "HIGH"
    assert result["prospectivity_score"] >= 70.0
    assert result["data_type"] == "statistical_prospectivity"
    assert "NOT a confirmed geological reserve" in result["disclaimer"]
    assert result["color"] == "red"


def test_low_zone_scores_low():
    result = get_prospectivity("D5")
    assert result is not None
    assert result["classification"] == "LOW"
    assert result["prospectivity_score"] < 40.0
    assert result["color"] == "green"


def test_cluster_ranks_above_background():
    high = [get_prospectivity(z)["prospectivity_score"] for z in ("B2", "B3", "C2", "C3")]
    low = [get_prospectivity(z)["prospectivity_score"] for z in ("A1", "A3", "D4", "D5")]
    assert min(high) > max(low) + 50


def test_unknown_zone_returns_none():
    assert get_prospectivity("ZZ9") is None


def test_all_zones_payload():
    payload = get_all_zones_prospectivity()
    assert payload["count"] == 20
    assert payload["data_type"] == "statistical_prospectivity"
    assert len(payload["zones"]) == 20
    sample = payload["zones"][0]
    assert set(sample) >= {"zone_id", "prospectivity_score", "classification", "color"}
    assert payload["thresholds"]["high"].startswith(">=")
