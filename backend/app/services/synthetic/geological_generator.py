"""Synthetic geological data generator — Phase 5.

Builds GEOLOGICAL records for every zone with a DELIBERATE ground-truth
pattern (not noise), documented in docs/synthetic_data_assumptions.md:

- Ground-truth manganese-rich cluster: zones B2, B3, C2, C3
  (supports the PRD Section 44 demo "Zone B = 91% prospectivity").
- High-prospectivity zones get gondite lithology (the manganese-bearing
  unit of the Sausar Group in the Balaghat belt) and short fault/lineament
  distances — the structural controls real manganese ore follows.
- All other zones get background lithologies (laterite, shale, quartzite)
  and larger fault/lineament distances.

The RNG seed is fixed so generation is reproducible across runs and phases.
"""

from __future__ import annotations

import numpy as np
from numpy.random import Generator, default_rng

# Ground-truth manganese-rich cluster (see docs/synthetic_data_assumptions.md).
HIGH_PROSPECTIVITY_ZONES: frozenset[str] = frozenset({"B2", "B3", "C2", "C3"})

LITHOLOGY_UNITS: dict[str, str] = {
    "gondite": "Sausar Group - Mansar Formation (gondite)",
    "laterite": "Laterite capping (Quaternary)",
    "shale": "Sausar Group - Tirodi shales",
    "quartzite": "Sausar Group - Lohangi Formation (quartzite)",
}

HIGH_LITHOLOGIES: tuple[str, ...] = ("gondite", "gondite", "quartzite")
LOW_LITHOLOGIES: tuple[str, ...] = ("laterite", "shale", "quartzite", "shale", "laterite")

# Fault / lineament distances (metres). Structural proximity is the
# deliberate signal the Phase 12 prospectivity model should pick up.
FAULT_DISTANCE_RANGE_HIGH = (120.0, 600.0)
FAULT_DISTANCE_RANGE_LOW = (700.0, 3000.0)
LINEAMENT_DISTANCE_RANGE_HIGH = (150.0, 700.0)
LINEAMENT_DISTANCE_RANGE_LOW = (800.0, 3500.0)

# Centroid jitter in degrees (~±200–450 m) so points sit inside their cell.
JITTER_DEG = 0.004


def generate_grid_cells_for_dry_run() -> list:
    """Zone-like objects built from the AOI grid (no DB needed).

    Exposes the same interface the generator expects (zone_id, geometry),
    used by the seed script's --dry-run path and by tests.
    """
    from geoalchemy2.elements import WKBElement

    from app.core.mine_config import DEFAULT_GRID_COLS, DEFAULT_GRID_ROWS, DEFAULT_MINE_AOI
    from app.services.grid_generation import generate_grid_cells

    cells = generate_grid_cells(DEFAULT_MINE_AOI, rows=DEFAULT_GRID_ROWS, cols=DEFAULT_GRID_COLS)

    class FakeZone:
        def __init__(self, cell):
            self.zone_id = cell.zone_id
            self.geometry = WKBElement(cell.geometry.wkb, srid=4326)

    return [FakeZone(cell) for cell in cells]


def generate_geological_records(
    zones: list,
    rng_seed: int = 42,
) -> list[dict]:
    """Generate one GEOLOGICAL record dict per zone.

    Args:
        zones: iterable of Zone ORM rows (must expose zone_id and geometry).
        rng_seed: fixed seed for reproducibility.
    """
    from geoalchemy2.shape import to_shape

    rng: Generator = default_rng(rng_seed)

    records: list[dict] = []
    for zone in zones:
        zone_id = zone.zone_id
        is_high = zone_id in HIGH_PROSPECTIVITY_ZONES

        lithology = str(rng.choice(HIGH_LITHOLOGIES if is_high else LOW_LITHOLOGIES))
        geological_unit = LITHOLOGY_UNITS[lithology]

        fault_range = FAULT_DISTANCE_RANGE_HIGH if is_high else FAULT_DISTANCE_RANGE_LOW
        lineament_range = LINEAMENT_DISTANCE_RANGE_HIGH if is_high else LINEAMENT_DISTANCE_RANGE_LOW
        fault_distance = float(rng.uniform(*fault_range))
        lineament_distance = float(rng.uniform(*lineament_range))

        centroid = to_shape(zone.geometry).centroid
        lon = float(centroid.x + rng.uniform(-JITTER_DEG, JITTER_DEG))
        lat = float(centroid.y + rng.uniform(-JITTER_DEG, JITTER_DEG))

        records.append(
            {
                "location_id": f"SYN-GEO-{zone_id}",
                "zone_id": zone_id,
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "location": f"SRID=4326;POINT({lon:.6f} {lat:.6f})",
                "lithology": lithology,
                "geological_unit": geological_unit,
                "fault_distance": round(fault_distance, 1),
                "lineament_distance": round(lineament_distance, 1),
            }
        )
    return records
