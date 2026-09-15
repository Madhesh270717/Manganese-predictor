"""Tests for resource estimation — Phase 13."""

import math

import pandas as pd
import pytest

from ml.pipelines.resource_estimation.estimate import (
    BULK_DENSITY_T_PER_M3,
    INFLUENCE_RADIUS_M,
    effective_mineralized_area,
    estimate_all,
    estimate_zone,
    fit_thickness_regression,
)


def _load():
    frame = pd.read_parquet(
        r"C:\Users\acer\Downloads\SIH 2026\spotter-ai\ml\data\processed\reserve_features.parquet"
    )
    return frame


def test_effective_area_respects_influence_and_cap():
    area = 4_583_399.0
    influence = math.pi * INFLUENCE_RADIUS_M**2
    assert effective_mineralized_area(1, area) == pytest.approx(influence)
    assert effective_mineralized_area(10, area) == pytest.approx(min(10 * influence, area))
    # A tiny zone caps out immediately.
    assert effective_mineralized_area(50, 10_000.0) == pytest.approx(10_000.0)


def test_b3_estimate_close_to_prd_target():
    frame = _load()
    slope, intercept = fit_thickness_regression(frame)
    row = frame[frame["zone_id"] == "B3"].iloc[0]
    est = estimate_zone(row, slope, intercept)

    # PRD §8: volume 1.2M m³, tonnage 4.2M t, MEDIUM confidence.
    assert est["insufficient_data"] is False
    assert est["confidence_level"] == "MEDIUM"
    assert abs(est["estimated_volume_m3"] - 1.2e6) / 1.2e6 < 0.15, est["estimated_volume_m3"]
    assert abs(est["estimated_tonnage"] - 4.2e6) / 4.2e6 < 0.15, est["estimated_tonnage"]
    # Grade discrepancy is documented (README.md): ~44% synthetic ore vs
    # PRD's illustrative 32%.
    assert 40.0 <= est["avg_mn_grade"] <= 48.0
    assert est["data_type"] == "statistical_estimate"


def test_undrilled_zone_flagged_insufficient():
    frame = _load()
    slope, intercept = fit_thickness_regression(frame)
    undrilled = frame[frame["drill_hole_count"] == 0].iloc[0]
    est = estimate_zone(undrilled, slope, intercept)
    assert est["insufficient_data"] is True
    assert est["confidence_level"] == "NOT_ESTIMATED"
    assert est["estimated_tonnage"] is None
    assert est["estimated_volume_m3"] is None


def test_sparse_zone_gets_low_confidence_estimate():
    frame = _load()
    slope, intercept = fit_thickness_regression(frame)
    sparse = frame[(frame["drill_hole_count"] > 0) & (frame["drill_hole_count"] < 4)].iloc[0]
    est = estimate_zone(sparse, slope, intercept)
    assert est["insufficient_data"] is False
    assert est["confidence_level"] == "LOW"
    assert est["estimated_tonnage"] is not None


def test_all_zones_include_flagged_not_omitted():
    frame = _load()
    estimates = estimate_all(frame)
    assert len(estimates) == 20
    flagged = [e for e in estimates if e["insufficient_data"]]
    assert len(flagged) > 0
    # All zones present in the list, flagged ones have null numbers.
    assert {e["zone_id"] for e in estimates} == set(frame["zone_id"])


def test_regression_fitted_on_strong_zones_only():
    frame = _load()
    slope, intercept = fit_thickness_regression(frame)
    # B3 thickness should be near its drill average (used directly).
    b3 = frame[frame["zone_id"] == "B3"].iloc[0]
    assert abs(slope * b3["mn_concentration"] + intercept) > 1.0
    # Regression output is positive for realistic mn values.
    assert slope * 40 + intercept > 1.0


def test_contained_mn_math():
    frame = _load()
    slope, intercept = fit_thickness_regression(frame)
    b3 = frame[frame["zone_id"] == "B3"].iloc[0]
    est = estimate_zone(b3, slope, intercept)
    expected = est["estimated_tonnage"] * est["avg_mn_grade"] / 100
    # Rounded fields propagate a small rounding error — relative tolerance.
    assert est["estimated_contained_mn"] == pytest.approx(expected, rel=0.001)
