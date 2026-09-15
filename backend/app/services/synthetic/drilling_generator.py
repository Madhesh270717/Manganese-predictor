"""Synthetic exploration/drilling data generator — Phase 6.

Generates EXPLORATION drill-hole records with DELIBERATE sparsity (not
uniform coverage), mirroring real exploration programs where drilling
concentrates on the highest-prospectivity ground:

- Manganese-rich cluster (Phase 5 ground truth): B2=6, B3=10, C2=6, C3=8
  holes. B3 is the PRD §44 demo zone — its holes are designed so that the
  Phase 13 resource estimation can arrive near "Zone B ~91% prospectivity,
  ~4.2 Mt estimated ore".
- Background zones: 0, 1, or 2 holes (p=0.6/0.3/0.1), most get none. This
  sparsity is what separates model-inferred prospectivity from
  drilling-confirmed reserve (PRD §8 product rule).

Correlations (documented in docs/synthetic_data_assumptions.md §9):
- ore_thickness ~ zone geochemical mn_concentration (richer zones get
  thicker intersections) with per-hole noise
- mn_grade (assay) ~ zone mn_concentration + N(0, 3.5) — correlated with,
  but NOT a duplicate of, the zone-level geochemical value
- depth: 60–150 m in cluster zones (deeper exploration), 20–80 m elsewhere

All hole coordinates are sampled INSIDE the zone polygon (shapely
rejection sampling), so every point satisfies the FK zone's geometry.
"""

from __future__ import annotations

import numpy as np
from numpy.random import Generator, default_rng
from shapely.geometry import Point

from app.services.synthetic.geological_generator import HIGH_PROSPECTIVITY_ZONES

# Deterministic hole counts per cluster zone.
CLUSTER_DRILL_COUNTS: dict[str, int] = {"B2": 6, "B3": 10, "C2": 6, "C3": 8}

# Background zones: weighted draw from these counts (most get zero).
BACKGROUND_COUNTS = [0, 0, 0, 0, 0, 0, 1, 1, 1, 2]  # p(0)=0.6, p(1)=0.3, p(2)=0.1

# Depth ranges (metres).
DEPTH_RANGE_CLUSTER = (60.0, 150.0)
DEPTH_RANGE_BACKGROUND = (20.0, 80.0)

# Thickness model: thickness ~ mn * 0.085 + N(0, 0.45), clipped.
THICKNESS_COEFF = 0.085
THICKNESS_NOISE = 0.45
THICKNESS_CLIP = (0.5, 9.0)

# Assay model: mn_grade ~ zone_mn + N(0, 3.5), clipped.
GRADE_NOISE = 3.5
GRADE_CLIP = (5.0, 48.0)

# Assay grade floor when a zone has no geochemical record (background default).
DEFAULT_ZONE_MN = 15.0

# Drill density thresholds (holes per km^2).
DENSITY_LABELS = [
    (0.0, "NONE"),
    (0.5, "SPARSE"),
    (1.5, "MODERATE"),
    (float("inf"), "DENSE"),
]


def drill_counts_per_zone(
    zones: list,
    rng: Generator,
) -> dict[str, int]:
    """Deterministic hole counts per zone following the sparsity rules."""
    counts: dict[str, int] = {}
    for zone in sorted(zones, key=lambda z: z.zone_id):
        zone_id = zone.zone_id
        if zone_id in CLUSTER_DRILL_COUNTS:
            counts[zone_id] = CLUSTER_DRILL_COUNTS[zone_id]
        else:
            counts[zone_id] = int(rng.choice(BACKGROUND_COUNTS))
    return counts


def _random_point_in_polygon(polygon, rng: Generator) -> Point:
    """Uniform-ish point inside a polygon via bbox rejection sampling."""
    minx, miny, maxx, maxy = polygon.bounds
    for _ in range(200):
        point = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if polygon.contains(point):
            return point
    return polygon.representative_point()


def generate_drilling_records(
    zones: list,
    zone_mn: dict[str, float],
    rng_seed: int = 2026,
) -> list[dict]:
    """Generate EXPLORATION record dicts per the sparsity + correlation rules.

    Args:
        zones: iterable of Zone ORM rows (zone_id + PostGIS geometry).
        zone_mn: zone_id -> geochemical mn_concentration from Phase 5.
        rng_seed: fixed seed for reproducibility.
    """
    from geoalchemy2.shape import to_shape

    rng: Generator = default_rng(rng_seed)
    counts = drill_counts_per_zone(zones, rng)

    records: list[dict] = []
    for zone in sorted(zones, key=lambda z: z.zone_id):
        zone_id = zone.zone_id
        n_holes = counts[zone_id]
        polygon = to_shape(zone.geometry)
        is_cluster = zone_id in CLUSTER_DRILL_COUNTS
        mn = float(zone_mn.get(zone_id, DEFAULT_ZONE_MN))

        depth_range = DEPTH_RANGE_CLUSTER if is_cluster else DEPTH_RANGE_BACKGROUND

        for n in range(1, n_holes + 1):
            point = _random_point_in_polygon(polygon, rng)
            thickness = float(
                np.clip(mn * THICKNESS_COEFF + rng.normal(0, THICKNESS_NOISE), *THICKNESS_CLIP)
            )
            assay = float(np.clip(mn + rng.normal(0, GRADE_NOISE), *GRADE_CLIP))
            depth = float(rng.uniform(*depth_range))

            records.append(
                {
                    "drill_id": f"SYN-DH-{zone_id}-{n:02d}",
                    "zone_id": zone_id,
                    "latitude": round(point.y, 6),
                    "longitude": round(point.x, 6),
                    "location": f"SRID=4326;POINT({point.x:.6f} {point.y:.6f})",
                    "depth": round(depth, 1),
                    "ore_thickness": round(thickness, 2),
                    "mn_grade": round(assay, 2),
                }
            )
    return records


def compute_drill_density(hole_count: int, area_sq_m: float | None) -> dict:
    """Drill density per zone: holes/km^2 mapped to a qualitative label.

    Computed on the fly by the API (no materialized summary): hole counts
    are small (<= 10 per zone) and areas are static, so a derived value is
    cheaper than a materialized table. Can be materialized later if needed.
    """
    area_km2 = (area_sq_m or 0.0) / 1_000_000.0
    per_km2 = hole_count / area_km2 if area_km2 > 0 else 0.0

    label = "NONE"
    for threshold, candidate in DENSITY_LABELS:
        if per_km2 <= threshold or hole_count == 0:
            label = candidate
            break

    return {
        "hole_count": hole_count,
        "holes_per_km2": round(per_km2, 3),
        "label": label,
    }
