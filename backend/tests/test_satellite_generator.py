"""Tests for the satellite generators — Phase 7."""

from datetime import date

import numpy as np

from app.services.synthetic.geological_generator import (
    HIGH_PROSPECTIVITY_ZONES,
    generate_grid_cells_for_dry_run,
)
from app.services.synthetic.satellite_generator import (
    generate_satellite_records,
    lst_for_month,
    ndvi_for_month,
    soil_moisture_for_month,
    spectral_features,
)


def _records(dates, real_ndvi=None):
    zones = generate_grid_cells_for_dry_run()
    return generate_satellite_records(zones, dates, real_ndvi=real_ndvi), zones


def test_time_series_covers_all_zones_and_dates():
    dates = [date(2026, 6, 1), date(2026, 7, 1), date(2026, 8, 1)]
    records, zones = _records(dates)
    assert len(records) == len(zones) * len(dates)
    by_zone_date = {(r["zone_id"], r["date"].isoformat()) for r in records}
    for z in zones:
        for d in dates:
            assert (z.zone_id, d.isoformat()) in by_zone_date


def test_soil_moisture_higher_in_monsoon():
    rng = np.random.default_rng(1)
    monsoon = [soil_moisture_for_month(8, False, rng) for _ in range(50)]
    dry = [soil_moisture_for_month(2, False, rng) for _ in range(50)]
    assert np.mean(monsoon) > np.mean(dry) + 5


def test_lst_cooler_in_monsoon():
    rng = np.random.default_rng(2)
    monsoon = [lst_for_month(8, False, rng) for _ in range(50)]
    hot = [lst_for_month(4, False, rng) for _ in range(50)]
    assert np.mean(hot) > np.mean(monsoon)


def test_ndvi_cluster_offset_lower():
    rng = np.random.default_rng(3)
    cluster = [ndvi_for_month(8, True, rng) for _ in range(50)]
    background = [ndvi_for_month(8, False, rng) for _ in range(50)]
    assert np.mean(background) > np.mean(cluster)


def test_spectral_features_cluster_elevated_iron():
    rng = np.random.default_rng(4)
    cluster = [spectral_features("B3", rng)["iron_oxide_ratio_b4_b2"] for _ in range(50)]
    background = [spectral_features("A1", rng)["iron_oxide_ratio_b4_b2"] for _ in range(50)]
    assert np.mean(cluster) > np.mean(background)


def test_records_carry_ndvi_source_tag():
    dates = [date(2026, 8, 1)]
    real_ndvi = {"2026-08-01": {z.zone_id: 0.5 for z in generate_grid_cells_for_dry_run()}}
    records, _ = _records(dates, real_ndvi=real_ndvi)
    assert all(r["spectral_features"]["ndvi_source"] == "real" for r in records)
    assert all(r["ndvi"] == 0.5 for r in records)

    records_synth, _ = _records(dates)
    assert all(r["spectral_features"]["ndvi_source"] == "synthetic" for r in records_synth)


def test_seasonal_variation_exists_in_series():
    dates = [date(2026, m, 1) for m in range(1, 13)]
    records, _ = _records(dates)
    b3 = [r for r in records if r["zone_id"] == "B3"]
    sm_values = [r["soil_moisture"] for r in b3]
    # Monsoon months (Jul-Sep) should exceed the annual mean.
    monsoon = [r["soil_moisture"] for r in b3 if r["date"].month in (7, 8, 9)]
    assert np.mean(monsoon) > np.mean(sm_values)


def test_reproducible_with_fixed_seed():
    dates = [date(2026, 8, 1), date(2026, 9, 1)]
    r1, _ = _records(dates)
    r2, _ = _records(dates)
    assert r1 == r2
