"""Mine area-of-interest (AOI) configuration — Phase 4.

DATA PROVENANCE NOTE
--------------------
The AOI below is an ILLUSTRATIVE bounding box, NOT an actual licensed
MOIL lease boundary. It approximates the manganese mining belt around the
Balaghat district (Madhya Pradesh, India), near the Nagpur–Balaghat
manganese belt where MOIL operates. It is provided so the prototype has a
spatially plausible region to build the zone grid on.

Sources of the approximation: public knowledge of the Balaghat belt location
(~21.6–21.9° N, ~79.7–80.2° E). Do NOT treat this polygon as a legal or
operational boundary. See docs/synthetic_data_assumptions.md.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MineAOI:
    mine_id: str
    mine_name: str
    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)


# Illustrative AOI: ~10.2 km E-W × ~8.9 km N-S around the Balaghat belt.
BALAGHAT_AOI = MineAOI(
    mine_id="MOIL-BALAGHAT",
    mine_name="Balaghat belt (illustrative AOI, not a real lease boundary)",
    min_lon=79.68,
    max_lon=79.78,
    min_lat=21.62,
    max_lat=21.70,
)

DEFAULT_MINE_AOI = BALAGHAT_AOI

# Default grid shape: 4 rows (A–D, north → south) × 5 columns (1–5, west → east).
DEFAULT_GRID_ROWS = 4
DEFAULT_GRID_COLS = 5
