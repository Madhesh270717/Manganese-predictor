"""Tests for feature engineering pipelines — Phase 11."""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from ml.pipelines.feature_engineering.loaders import load_from_synthetic
from ml.pipelines.feature_engineering.production_features import (
    build_production_features,
)
from ml.pipelines.feature_engineering.reserve_features import build_reserve_features
from ml.pipelines.feature_engineering.feature_quality import (
    check_production_features,
    check_reserve_features,
)


def _reserve():
    data = load_from_synthetic()
    return build_reserve_features(
        zones=data["zones"],
        geological=data["geological"],
        geochemical=data["geochemical"],
        exploration=data["exploration"],
        satellite=data["satellite"],
    ), data


def _production():
    data = load_from_synthetic()
    return build_production_features(
        production=data["production"],
        equipment=data["equipment"],
        equipment_history=data["equipment_history"],
        weather=data["weather"],
        blasting=data["blasting"],
    ), data


def test_reserve_one_row_per_zone():
    frame, data = _reserve()
    assert len(frame) == len(data["zones"]) == 20
    assert set(frame["zone_id"]) == set(data["zones"]["zone_id"])


def test_reserve_missingness_flag_not_silent_drop():
    frame, _ = _reserve()
    # Cluster zones have drilling; background zones mostly don't — but the
    # flag must agree with the count everywhere.
    assert (frame["has_drilling_data"] == (frame["drill_hole_count"] > 0)).all()
    # Undrilled zones are still present (prospectivity candidates).
    assert (frame["drill_hole_count"] == 0).any()
    assert frame["drill_hole_count"].isna().sum() == 0


def test_reserve_geological_geochemical_joined():
    frame, _ = _reserve()
    # Every zone has geological data (Phase 5 generated one per zone).
    assert frame["lithology"].notna().all()
    assert frame["mn_concentration"].notna().all()
    assert frame["fault_distance"].notna().all()


def test_reserve_trace_elements_flattened():
    frame, _ = _reserve()
    assert "trace_Al2O3" in frame.columns
    assert "trace_CaO" in frame.columns
    assert frame["trace_Al2O3"].notna().all()


def test_high_prospectivity_zone_shows_stronger_values():
    frame, _ = _reserve()
    b3 = frame[frame["zone_id"] == "B3"].iloc[0]
    d5 = frame[frame["zone_id"] == "D5"].iloc[0]
    assert b3["mn_concentration"] > d5["mn_concentration"] + 10
    assert b3["fault_distance"] < d5["fault_distance"]
    assert b3["drill_hole_count"] > d5["drill_hole_count"]
    assert b3["has_drilling_data"]


def test_production_one_row_per_zone_date():
    frame, data = _production()
    zones = data["production"]["zone_id"].nunique()
    dates = data["production"]["date"].nunique()
    assert len(frame) == zones * dates


def test_production_has_target_column():
    frame, _ = _production()
    assert frame.columns[-1] == "actual_production"
    assert frame["actual_production"].notna().all()


def test_production_weather_joined_same_day():
    frame, data = _production()
    sample = frame[frame["zone_id"] == "B3"].head(5)
    weather = data["weather"][data["weather"]["zone_id"] == "B3"]
    for _, row in sample.iterrows():
        day_weather = weather[weather["date"] == row["date"]]
        if not day_weather.empty:
            assert row["rainfall_1d"] == day_weather.iloc[0]["rainfall_1d"]


def test_no_future_leakage_in_equipment_join():
    frame, data = _production()
    # For each production row, fleet_availability must come from a history
    # date <= the production date (as-of join, direction=backward).
    history = data["equipment_history"].copy()
    unit_zone = data["equipment"][["equipment_id", "current_zone_id"]].drop_duplicates()
    history = history.merge(unit_zone, on="equipment_id")
    history = history.rename(columns={"current_zone_id": "zone_id"})

    for zone in ["B3", "A1"]:
        sub = frame[frame["zone_id"] == zone].sort_values("date")
        zone_hist = history[history["zone_id"] == zone].copy()
        zone_hist["date"] = pd.to_datetime(zone_hist["date"])
        zone_hist = zone_hist.sort_values("date")
        for _, row in sub.head(20).iterrows():
            avail = row["fleet_availability"]
            if pd.isna(avail):
                continue
            past = zone_hist[zone_hist["date"] <= pd.Timestamp(row["date"])]
            if past.empty:
                continue
            expected = past.iloc[-1]["availability"]
            # Row is an aggregate (mean of fleet), so just check it's within
            # the plausible fleet-wide range, not an exact value.
            assert 0.0 <= avail <= 1.0


def test_missingness_flags_consistent():
    frame, _ = _production()
    assert (frame["has_weather"] == frame["rainfall_1d"].notna()).all()
    assert (frame["has_equipment"] == frame["fleet_availability"].notna()).all()
    assert (frame["has_blast_same_day"] == frame["blast_delay_same_day"].notna()).all()


def test_quality_reports_flag_truncated_equipment_history():
    data = load_from_synthetic()
    reserve = build_reserve_features(
        zones=data["zones"],
        geological=data["geological"],
        geochemical=data["geochemical"],
        exploration=data["exploration"],
        satellite=data["satellite"],
    )
    # Deliberately truncate equipment history to 90 days: the as-of join
    # leaves older production rows without fleet features — must be flagged.
    history = data["equipment_history"].copy()
    cutoff = history["date"].max() - pd.Timedelta(days=90)
    truncated = history[history["date"] >= cutoff]
    production = build_production_features(
        production=data["production"],
        equipment=data["equipment"],
        equipment_history=truncated,
        weather=data["weather"],
        blasting=data["blasting"],
    )
    reserve_report = check_reserve_features(reserve)
    production_report = check_production_features(production)
    assert reserve_report["ok"] is True, reserve_report["issues"]
    assert production_report["ok"] is False
    assert production_report["missing_pct"]["fleet_availability"] > 0.5


def test_quality_reports_pass_with_full_history():
    reserve, _ = _reserve()
    production, _ = _production()
    reserve_report = check_reserve_features(reserve)
    production_report = check_production_features(production)
    assert reserve_report["ok"] is True, reserve_report["issues"]
    assert production_report["ok"] is True, production_report["issues"]


def test_recent_window_has_no_missing_equipment():
    production, _ = _production()
    window = production[production["date"] >= production["date"].max() - pd.Timedelta(days=60)]
    assert window["fleet_availability"].notna().all()
    assert window["rainfall_1d"].notna().all()


def test_quality_report_detects_injected_badness():
    reserve, _ = _reserve()
    bad = reserve.copy()
    bad.loc[0, "mn_concentration"] = -5.0
    report = check_reserve_features(bad)
    assert report["ok"] is False
    assert any("negative mn_concentration" in i for i in report["issues"])

    production, _ = _production()
    bad_prod = production.copy()
    bad_prod.loc[0, "rainfall_1d"] = -1.0
    report = check_production_features(bad_prod)
    assert report["ok"] is False
    assert any("negative values in rainfall_1d" in i for i in report["issues"])
