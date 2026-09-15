"""Tests for the synthetic drilling generator — Phase 6."""

from collections import Counter

import numpy as np
from shapely.geometry import Polygon, Point

from app.services.synthetic.drilling_generator import (
    CLUSTER_DRILL_COUNTS,
    compute_drill_density,
    generate_drilling_records,
)
from app.services.synthetic.geochemical_generator import generate_geochemical_records
from app.services.synthetic.geological_generator import (
    HIGH_PROSPECTIVITY_ZONES,
    generate_geological_records,
    generate_grid_cells_for_dry_run,
)


def _records():
    zones = generate_grid_cells_for_dry_run()
    geo = generate_geological_records(zones)
    chem = generate_geochemical_records(geo)
    mn_map = {g["zone_id"]: c["mn_concentration"] for g, c in zip(geo, chem)}
    return generate_drilling_records(zones, mn_map), zones, mn_map


def test_sparsity_pattern_cluster_dense_background_mostly_empty():
    records, zones, _ = _records()
    counts = Counter(r["zone_id"] for r in records)
    for zone_id, expected in CLUSTER_DRILL_COUNTS.items():
        assert counts[zone_id] == expected, zone_id

    background = [z.zone_id for z in zones if z.zone_id not in CLUSTER_DRILL_COUNTS]
    bg_counts = [counts[z] for z in background]
    assert all(c in {0, 1, 2} for c in bg_counts)
    zeros = sum(1 for c in bg_counts if c == 0)
    assert zeros >= len(background) // 2, "most background zones should be undrilled"


def test_cluster_zones_have_more_holes_than_background():
    records, zones, _ = _records()
    counts = Counter(r["zone_id"] for r in records)
    cluster_total = sum(counts[z] for z in CLUSTER_DRILL_COUNTS)
    background_total = sum(
        counts[z.zone_id] for z in zones if z.zone_id not in CLUSTER_DRILL_COUNTS
    )
    assert cluster_total > background_total


def test_all_holes_fall_inside_their_zone_polygon():
    records, zones, _ = _records()
    polygons = {z.zone_id: _polygon_from_zone(z) for z in zones}
    for r in records:
        polygon = polygons[r["zone_id"]]
        assert polygon.contains(Point(r["longitude"], r["latitude"])), r["drill_id"]


def _polygon_from_zone(zone):
    from geoalchemy2.shape import to_shape

    return to_shape(zone.geometry)


def test_drill_ids_are_syn_prefixed_and_unique():
    records, _, _ = _records()
    ids = [r["drill_id"] for r in records]
    assert len(ids) == len(set(ids))
    assert all(i.startswith("SYN-DH-") for i in ids)


def test_thickness_correlates_with_zone_mn():
    records, _, mn_map = _records()
    for r in records:
        zone_mn = mn_map[r["zone_id"]]
        # Expected thickness within ±3 sigma of the linear model.
        expected = zone_mn * 0.085
        assert abs(r["ore_thickness"] - expected) < 0.45 * 4 + 0.01, r["drill_id"]
        assert 0.5 <= r["ore_thickness"] <= 9.0


def test_grade_correlates_but_not_duplicates_zone_mn():
    records, _, mn_map = _records()
    for r in records:
        zone_mn = mn_map[r["zone_id"]]
        assert abs(r["mn_grade"] - zone_mn) < 3.5 * 4 + 0.01, r["drill_id"]
        assert 5.0 <= r["mn_grade"] <= 48.0

    # Grades are noisy samples, not the zone value itself.
    b3_grades = [r["mn_grade"] for r in records if r["zone_id"] == "B3"]
    assert len(set(b3_grades)) > 1


def test_cluster_grades_higher_than_background_grades():
    records, _, _ = _records()
    cluster = [r["mn_grade"] for r in records if r["zone_id"] in CLUSTER_DRILL_COUNTS]
    background = [r["mn_grade"] for r in records if r["zone_id"] not in CLUSTER_DRILL_COUNTS]
    assert np.mean(cluster) > np.mean(background)


def test_b3_demo_zone_supports_prd_targets():
    records, _, _ = _records()
    b3 = [r for r in records if r["zone_id"] == "B3"]
    assert len(b3) == 10
    mean_grade = np.mean([r["mn_grade"] for r in b3])
    mean_thickness = np.mean([r["ore_thickness"] for r in b3])
    # Designed to land near PRD §44 figures (see synthetic_data_assumptions.md §9.4).
    # Phase 5 B3 zone mn ≈ 43.9%, so assays center ~44% with ±3.5 noise.
    assert 38.0 <= mean_grade <= 46.0
    assert 2.5 <= mean_thickness <= 4.5


def test_drill_density_labels():
    assert compute_drill_density(0, 4_500_000.0)["label"] == "NONE"
    assert compute_drill_density(1, 4_500_000.0)["label"] == "SPARSE"
    assert compute_drill_density(6, 4_500_000.0)["label"] == "MODERATE"
    assert compute_drill_density(10, 4_500_000.0)["label"] == "DENSE"
    # B3: 10 holes / ~4.58 km^2 ≈ 2.2 per km^2.
    density = compute_drill_density(10, 4_583_399.0)
    assert density["holes_per_km2"] == 2.182
    assert density["label"] == "DENSE"


def test_generation_is_reproducible():
    r1, _, _ = _records()
    r2, _, _ = _records()
    assert r1 == r2
