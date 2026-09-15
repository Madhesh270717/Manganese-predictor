"""Tests for the synthetic geological + geochemical generators — Phase 5."""

import numpy as np

from app.services.synthetic.geochemical_generator import (
    generate_geochemical_records,
)
from app.services.synthetic.geological_generator import (
    HIGH_PROSPECTIVITY_ZONES,
    generate_geological_records,
    generate_grid_cells_for_dry_run,
)


def _records():
    zones = generate_grid_cells_for_dry_run()
    return generate_geological_records(zones), zones


def test_every_zone_gets_a_geological_record():
    geo, zones = _records()
    assert len(geo) == len(zones) == 20
    assert {r["zone_id"] for r in geo} == {z.zone_id for z in zones}


def test_geochemical_one_to_one_with_geological():
    geo, _ = _records()
    chem = generate_geochemical_records(geo)
    assert len(chem) == len(geo)
    assert {c["location_id"] for c in chem} == {g["location_id"] for g in geo}


def test_syn_prefix_on_ids():
    geo, _ = _records()
    assert all(r["location_id"].startswith("SYN-GEO-") for r in geo)
    assert geo[0]["location_id"] == "SYN-GEO-A1"


def test_ground_truth_cluster_has_gondite_and_short_distances():
    geo, _ = _records()
    by_zone = {r["zone_id"]: r for r in geo}
    for zone_id in HIGH_PROSPECTIVITY_ZONES:
        record = by_zone[zone_id]
        assert record["lithology"] in {"gondite", "quartzite"}, zone_id
        assert record["fault_distance"] <= 600.0, zone_id
        assert record["lineament_distance"] <= 700.0, zone_id


def test_background_zones_have_larger_structural_distances():
    geo, _ = _records()
    for r in geo:
        if r["zone_id"] not in HIGH_PROSPECTIVITY_ZONES:
            assert r["fault_distance"] >= 700.0, r["zone_id"]
            assert r["lineament_distance"] >= 800.0, r["zone_id"]


def test_geochemical_ranges_are_realistic():
    geo, _ = _records()
    chem = generate_geochemical_records(geo)
    geo_by_loc = {g["location_id"]: g for g in geo}
    for c in chem:
        zone_id = geo_by_loc[c["location_id"]]["zone_id"]
        is_high = zone_id in HIGH_PROSPECTIVITY_ZONES
        if is_high:
            assert 30.0 <= c["mn_concentration"] <= 46.0, zone_id
            assert 4.0 <= c["fe_concentration"] <= 9.0, zone_id
            assert 8.0 <= c["sio2"] <= 22.0, zone_id
        else:
            assert 8.0 <= c["mn_concentration"] <= 24.0, zone_id
            assert 2.0 <= c["fe_concentration"] <= 7.0, zone_id
            assert 25.0 <= c["sio2"] <= 55.0, zone_id
        assert set(c["other_elements"]) == {"Al2O3", "CaO", "P", "P2O5"}


def test_cluster_mn_means_higher_than_background():
    geo, _ = _records()
    chem = generate_geochemical_records(geo)
    geo_by_loc = {g["location_id"]: g for g in geo}
    high = [c for c in chem if geo_by_loc[c["location_id"]]["zone_id"] in HIGH_PROSPECTIVITY_ZONES]
    low = [c for c in chem if geo_by_loc[c["location_id"]]["zone_id"] not in HIGH_PROSPECTIVITY_ZONES]
    assert np.mean([c["mn_concentration"] for c in high]) > np.mean(
        [c["mn_concentration"] for c in low]
    )


def test_generation_is_reproducible_with_fixed_seed():
    zones1 = generate_grid_cells_for_dry_run()
    zones2 = generate_grid_cells_for_dry_run()
    geo1 = generate_geological_records(zones1)
    geo2 = generate_geological_records(zones2)
    assert geo1 == geo2
    assert generate_geochemical_records(geo1) == generate_geochemical_records(geo2)
