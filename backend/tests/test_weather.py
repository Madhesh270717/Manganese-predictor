"""Tests for the weather generator + service — Phase 8."""

from datetime import date, timedelta

import numpy as np

from app.services.synthetic.weather_generator import (
    AT_RISK_ZONE,
    FAVORABLE_ZONE,
    generate_demo_scenario,
    generate_historical_baseline,
    rolling_sum,
)


def _zones():
    return [type("Z", (), {"zone_id": f"{r}{c}"})() for r in "ABCD" for c in "12345"]


def _twelve_months():
    end = date(2026, 8, 1)
    return [end - timedelta(days=30 * i) for i in range(11, -1, -1)]


def test_baseline_covers_all_zones_and_dates():
    zones = _zones()
    dates = _twelve_months()
    records = generate_historical_baseline(zones, dates)
    assert len(records) == len(zones) * len(dates)
    assert {r["scenario"] for r in records} == {"historical"}


def test_rolling_sums_internally_consistent():
    # Build a tiny series and verify 1d/7d/30d are true rolling sums.
    series = {date(2026, 8, 1): 10.0, date(2026, 8, 2): 5.0, date(2026, 8, 3): 2.0}
    assert rolling_sum(series, 1, date(2026, 8, 3)) == 2.0
    assert rolling_sum(series, 7, date(2026, 8, 3)) == 17.0
    assert rolling_sum(series, 30, date(2026, 8, 3)) == 17.0


def test_monsoon_wetter_than_dry_season():
    zones = _zones()
    dates = _twelve_months()
    records = generate_historical_baseline(zones, dates)
    monsoon = [r["rainfall_1d"] for r in records if r["date"].month in (7, 8)]
    dry = [r["rainfall_1d"] for r in records if r["date"].month in (1, 2)]
    assert np.mean(monsoon) > np.mean(dry) * 5


def test_zones_vary_but_correlated():
    zones = _zones()
    dates = _twelve_months()
    records = generate_historical_baseline(zones, dates)
    by_zone = {}
    for r in records:
        by_zone.setdefault(r["zone_id"], []).append(r["rainfall_1d"])
    means = {z: np.mean(v) for z, v in by_zone.items()}
    assert len(set(round(m, 2) for m in means.values())) > 15, "zones should vary"
    # Correlated: monsoon means stay in a sane band despite per-zone factors.
    assert max(means.values()) / min(means.values()) < 10


def test_demo_scenario_spikes_at_risk_zone():
    zones = _zones()
    trigger = date(2026, 8, 20)
    dates = [trigger - timedelta(days=i) for i in range(6, -1, -1)]
    records = generate_demo_scenario(zones, dates, spike_date=trigger)

    a1 = [r for r in records if r["zone_id"] == AT_RISK_ZONE and r["date"] == trigger][0]
    assert a1["rainfall_1d"] == 110.0
    assert a1["rainfall_7d"] >= 150.0

    b3 = [r for r in records if r["zone_id"] == FAVORABLE_ZONE and r["date"] == trigger][0]
    assert b3["rainfall_1d"] < 5.0
    assert b3["rainfall_7d"] < 20.0

    assert {r["scenario"] for r in records} == {"demo"}


def test_risk_alert_scan_flags_at_risk_zone():
    from app.services.weather_service import scan_risk_alerts

    zones = _zones()
    trigger = date(2026, 8, 20)
    dates = [trigger - timedelta(days=i) for i in range(6, -1, -1)]
    records = generate_demo_scenario(zones, dates, spike_date=trigger)

    class FakeRow:
        def __init__(self, record):
            self.zone_id = record["zone_id"]
            self.date = record["date"]
            self.rainfall_1d = record["rainfall_1d"]
            self.rainfall_7d = record["rainfall_7d"]
            self.rainfall_30d = record["rainfall_30d"]

    trigger_rows = [FakeRow(r) for r in records if r["date"] == trigger]

    class FakeSession:
        def scalars(self, stmt):
            from app.models import Weather

            entity = stmt.column_descriptions[0]["entity"]
            if entity is Weather:
                if "distinct" in str(stmt).lower():
                    return ScalarList(list({r.zone_id for r in trigger_rows}))
                return ScalarList(trigger_rows)
            return ScalarList([])

        def scalar(self, stmt):
            return None

    class ScalarList:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    report = scan_risk_alerts(FakeSession(), on_date=trigger)
    flagged = {a["zone_id"] for a in report["alerts"]}
    assert AT_RISK_ZONE in flagged
    assert FAVORABLE_ZONE not in flagged


def test_latest_weather_fallback_stale_flag():
    from app.services.weather_service import latest_weather

    class FakeRow:
        def __init__(self, zone_id, d, rain):
            self.zone_id = zone_id
            self.date = d
            self.rainfall_1d = rain
            self.rainfall_7d = rain * 3
            self.rainfall_30d = rain * 10

    last = FakeRow("A1", date(2026, 8, 15), 12.5)

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def scalar(self, stmt):
            self.calls += 1
            if self.calls == 1:
                return None  # no row for the requested date
            return last  # fallback: latest available

    result = latest_weather(FakeSession(), "A1", on_date=date(2026, 8, 20))
    assert result["is_stale"] is True
    assert result["data_age_days"] == 5
    assert result["rainfall_1d"] == 12.5
