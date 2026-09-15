"""Tests for production + schedule generators — Phase 10."""

from datetime import date, timedelta

import numpy as np

from app.services.synthetic.production_generator import (
    ACTIVE_ZONES,
    current_period_planned_total,
    generate_production_records,
)
from app.services.synthetic.schedule_generator import generate_current_schedule
from app.services.synthetic.weather_generator import AT_RISK_ZONE


def _dates(n=365):
    today = date.today()
    return [today - timedelta(days=i) for i in range(n - 1, -1, -1)]


def _mn_map():
    return {"A1": 15.0, "B2": 40.0, "B3": 43.9, "C2": 41.0, "C3": 42.0}


def test_production_covers_active_zones_and_dates():
    dates = _dates(90)
    records = generate_production_records(dates, _mn_map())
    assert len(records) == len(ACTIVE_ZONES) * len(dates)
    assert {r["zone_id"] for r in records} == set(ACTIVE_ZONES)


def test_current_period_planned_totals_82000():
    dates = _dates(365)
    total = current_period_planned_total(dates)
    assert total == 82000.0


def test_heavy_rain_reduces_actual_production():
    dates = _dates(30)
    rain_day = dates[-1]
    weather = {zone: {rain_day: 110.0} for zone in ACTIVE_ZONES}
    records = generate_production_records(dates, _mn_map(), weather_daily=weather)
    rainy = [r for r in records if r["date"] == rain_day]
    non_rainy = [r for r in records if r["date"] != rain_day]
    rain_ratio = np.mean([r["actual_production"] / r["planned_production"] for r in rainy])
    dry_ratio = np.mean([r["actual_production"] / r["planned_production"] for r in non_rainy])
    assert rain_ratio < dry_ratio


def test_low_availability_reduces_actual_production():
    dates = _dates(30)
    avail = {zone: {d: 0.5 for d in dates} for zone in ACTIVE_ZONES}
    records_low = generate_production_records(dates, _mn_map(), equipment_availability=avail)
    records_normal = generate_production_records(dates, _mn_map())
    low_ratio = np.mean([r["actual_production"] / r["planned_production"] for r in records_low])
    normal_ratio = np.mean([r["actual_production"] / r["planned_production"] for r in records_normal])
    assert low_ratio < normal_ratio


def test_ore_grade_tracks_zone_mn():
    dates = _dates(30)
    records = generate_production_records(dates, _mn_map())
    b3 = [r["ore_grade"] for r in records if r["zone_id"] == "B3"]
    a1 = [r["ore_grade"] for r in records if r["zone_id"] == "A1"]
    assert np.mean(b3) > np.mean(a1) + 15


def test_production_has_variation_not_flat():
    dates = _dates(90)
    records = generate_production_records(dates, _mn_map())
    ratios = {round(r["actual_production"] / r["planned_production"], 2) for r in records}
    assert len(ratios) > 25, "variation across days/zones should be substantial"
    assert any(r > 1.0 for r in ratios), "some over-target days should exist"


def test_schedule_has_ex04_in_at_risk_zone():
    schedule = generate_current_schedule(start_date=date.today(), days=3)
    ex04 = [s for s in schedule if s["equipment_id"] == "EX-04"]
    assert ex04, "EX-04 should be scheduled"
    assert all(s["zone_id"] == AT_RISK_ZONE for s in ex04)
    assert all(s["operation"] == "excavation" for s in ex04)
    # Future shifts are proposed; today-or-earlier are active.
    today_rows = [s for s in schedule if s["date"] == date.today()]
    assert {s["status"] for s in today_rows} == {"active"}


def test_schedule_covers_all_units_and_two_shifts():
    schedule = generate_current_schedule(start_date=date.today(), days=1)
    assert len(schedule) == 10 * 2
    assert {s["shift"] for s in schedule} == {"A", "B"}
    assert len({s["equipment_id"] for s in schedule}) == 10
