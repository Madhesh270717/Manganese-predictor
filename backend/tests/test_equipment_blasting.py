"""Tests for equipment + blasting generators — Phase 9."""

from datetime import date, timedelta

import numpy as np

from app.services.synthetic.blasting_generator import generate_blasting_records
from app.services.synthetic.equipment_generator import (
    FLEET_SPEC,
    generate_equipment_fleet,
    generate_status_history,
)
from app.services.synthetic.geological_generator import (
    generate_grid_cells_for_dry_run,
)
from app.services.synthetic.weather_generator import AT_RISK_ZONE


def test_fleet_size_and_id_scheme():
    fleet = generate_equipment_fleet()
    assert len(fleet) == 10
    ids = {u["equipment_id"] for u in fleet}
    assert "EX-04" in ids and "T-07" in ids and "DR-08" in ids and "LD-10" in ids
    assert all(u["mine_id"] == "MOIL-BALAGHAT" for u in fleet)


def test_ex04_assigned_to_at_risk_zone_with_degraded_availability():
    fleet = generate_equipment_fleet()
    ex04 = next(u for u in fleet if u["equipment_id"] == "EX-04")
    assert ex04["current_zone_id"] == AT_RISK_ZONE
    assert ex04["availability"] < 0.70
    # Downtime story: ~41% of scheduled hours.
    assert 3.0 <= ex04["downtime_hours"] <= 6.0


def test_availability_varies_across_fleet():
    fleet = generate_equipment_fleet()
    availabilities = {u["availability"] for u in fleet}
    assert len(availabilities) > 5
    assert max(availabilities) < 1.0


def test_history_series_per_unit_with_variation():
    fleet = generate_equipment_fleet()
    history = generate_status_history(fleet, days=30)
    assert len(history) == 10 * 30
    ex04 = [h for h in history if h["equipment_id"] == "EX-04"]
    avails = {h["availability"] for h in ex04}
    assert len(avails) > 10, "history should vary day to day"


def test_blasting_concentrates_on_active_zones():
    zones = generate_grid_cells_for_dry_run()
    records = generate_blasting_records(zones, weather_daily={})
    by_zone = {r["zone_id"] for r in records}
    assert by_zone <= {"B2", "B3", "C2", "C3", "A1"}
    assert "B3" in by_zone and "A1" in by_zone
    # Background zones get no blasts.
    assert "D5" not in by_zone


def test_blasting_delays_correlate_with_rain():
    zones = generate_grid_cells_for_dry_run()
    # Rain on several days inside the 1-week window so at least one blast
    # date is wet (blast offsets land on today-1/-3/-5 for A1).
    weather = {
        AT_RISK_ZONE: {
            date.today() - timedelta(days=i): 110.0 for i in range(1, 7)
        }
    }
    records = generate_blasting_records(zones, weather_daily=weather, n_weeks=1)
    a1 = [r for r in records if r["zone_id"] == AT_RISK_ZONE]
    assert a1, "A1 should have blast records in a 1-week window"
    # Rain-correlated delays (110mm * 0.05 = ~5.5h expected) are visible.
    delayed = [r for r in a1 if r["delay_hours"] > 2.0]
    assert delayed, "rain-correlated delays should be visible"


def test_blasting_ids_are_syn_prefixed():
    zones = generate_grid_cells_for_dry_run()
    records = generate_blasting_records(zones, weather_daily={})
    assert all(r["blast_id"].startswith("SYN-BL-") for r in records)
    ids = {r["blast_id"] for r in records}
    assert len(ids) == len(records)
