"""Synthetic terrain/access generator — Phase 14.

Deliberate pattern (documented in docs/synthetic_data_assumptions.md §15):
the high-prospectivity cluster (B2/B3/C2/C3) is ALSO the operationally
favorable ground — gentle slopes, GOOD access, short haul, GOOD roads —
because PRD §20's example shows Zone B as simultaneously HIGH Mn
prospectivity AND HIGH mineability. A1 (the at-risk zone) is deliberately
POOR on access/road (rain-susceptible terrain) to justify the Phase 18+
move away from it.

Haul distance is computed from the zone centroid to the AOI's southwest
corner (assumed processing plant location — documented simplification).
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from numpy.random import Generator, default_rng

from app.services.synthetic.geological_generator import HIGH_PROSPECTIVITY_ZONES
from app.services.synthetic.weather_generator import AT_RISK_ZONE

# Assumed processing plant anchor: AOI south-center, near the cluster
# (documented simplification — PRD §20's Zone B must have GOOD access).
PLANT_LON = 79.73
PLANT_LAT = 21.63

SLOPE_CLUSTER = (2.0, 8.0)
SLOPE_BACKGROUND = (8.0, 25.0)
SLOPE_AT_RISK = (10.0, 20.0)

HAUL_BASE = 1.2  # km floor
HAUL_CLUSTER = (1.5, 4.0)
HAUL_BACKGROUND = (4.0, 9.0)


def _distance_km(lon: float, lat: float) -> float:
    # Equirectangular approximation (documented simplification).
    dx = (lon - PLANT_LON) * 111.32 * np.cos(np.radians((lat + PLANT_LAT) / 2))
    dy = (lat - PLANT_LAT) * 110.54
    return float(np.hypot(dx, dy))


def generate_terrain_records(
    zones: list,
    rng_seed: int = 14,
) -> list[dict]:
    """One terrain/access record per zone."""
    from geoalchemy2.shape import to_shape

    rng: Generator = default_rng(rng_seed)
    records: list[dict] = []
    for zone in zones:
        zone_id = zone.zone_id
        centroid = to_shape(zone.geometry).centroid

        if zone_id in HIGH_PROSPECTIVITY_ZONES:
            slope = float(rng.uniform(*SLOPE_CLUSTER))
            accessibility = "GOOD"
            road = "GOOD"
            haul = float(rng.uniform(*HAUL_CLUSTER))
        elif zone_id == AT_RISK_ZONE:
            slope = float(rng.uniform(*SLOPE_AT_RISK))
            accessibility = "MODERATE"
            road = "POOR"  # rain-susceptible — the demo narrative
            haul = float(rng.uniform(*HAUL_BACKGROUND))
        else:
            slope = float(rng.uniform(*SLOPE_BACKGROUND))
            accessibility = "MODERATE" if rng.random() < 0.6 else "POOR"
            road = "MODERATE" if rng.random() < 0.5 else "POOR"
            haul = float(rng.uniform(*HAUL_BACKGROUND))

        # Haul distance from centroid geometry (documented computation).
        haul = max(HAUL_BASE, _distance_km(centroid.x, centroid.y) + rng.normal(0, 0.4))

        records.append(
            {
                "zone_id": zone_id,
                "slope_degrees": round(slope, 1),
                "accessibility_rating": accessibility,
                "haul_distance_km": round(haul, 2),
                "road_condition": road,
            }
        )
    return records
