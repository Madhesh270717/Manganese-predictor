"""Synthetic equipment fleet generator — Phase 9.

Generates a realistic 10-unit manganese mining fleet with PRD-style IDs
(EX- = excavator, T- = truck/dumper, DR- = drill rig, LD- = loader).

Deliberate demo setup (documented in docs/synthetic_data_assumptions.md §13):
- EX-04 is assigned to the AT-RISK zone (A1, the Phase 8 rainfall spike
  zone) — the unit the Phase 18+ optimizer will recommend moving to B3.
- EX-04 has degraded availability (~59%): its downtime story (downtime 41%
  of scheduled hours) is designed to justify the PRD §16 explainability
  example "Equipment downtime 41%" as the largest shortfall contributor.

Time series: the fleet table stores the CURRENT snapshot; per-unit daily
history lives in EQUIPMENT_STATUS_HISTORY (migration 0004). Each unit's
90-day series has realistic variation (not flat 100%).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from numpy.random import Generator, default_rng

from app.services.synthetic.weather_generator import AT_RISK_ZONE

# --- fleet definition: (equipment_id, type, zone, base_availability, capacity t/h) ---

FLEET_SPEC: list[dict] = [
    {"equipment_id": "EX-01", "equipment_type": "Excavator", "zone_id": "C2", "base_availability": 0.90, "capacity": 120.0},
    {"equipment_id": "EX-02", "equipment_type": "Excavator", "zone_id": "B2", "base_availability": 0.86, "capacity": 115.0},
    {"equipment_id": "EX-03", "equipment_type": "Excavator", "zone_id": "C3", "base_availability": 0.88, "capacity": 120.0},
    # Demo unit: at-risk zone + degraded availability (41% downtime story).
    {"equipment_id": "EX-04", "equipment_type": "Excavator", "zone_id": AT_RISK_ZONE, "base_availability": 0.59, "capacity": 110.0},
    {"equipment_id": "EX-05", "equipment_type": "Excavator", "zone_id": "B3", "base_availability": 0.91, "capacity": 125.0},
    {"equipment_id": "T-06", "equipment_type": "Dumper/Truck", "zone_id": "B3", "base_availability": 0.84, "capacity": 60.0},
    {"equipment_id": "T-07", "equipment_type": "Dumper/Truck", "zone_id": "B2", "base_availability": 0.82, "capacity": 55.0},
    {"equipment_id": "DR-08", "equipment_type": "Drill Rig", "zone_id": "C3", "base_availability": 0.78, "capacity": 30.0},
    {"equipment_id": "DR-09", "equipment_type": "Drill Rig", "zone_id": "B3", "base_availability": 0.80, "capacity": 32.0},
    {"equipment_id": "LD-10", "equipment_type": "Loader", "zone_id": "C2", "base_availability": 0.87, "capacity": 90.0},
]

MINE_ID = "MOIL-BALAGHAT"

SHIFT_HOURS = 12.0  # hours/day scheduled
AVAILABILITY_NOISE = 0.04
MAINTENANCE_EVENT_P = 0.06  # daily chance of a maintenance dip
MAINTENANCE_DIP = 0.35


def _availability_for_day(unit: dict, rng: Generator) -> float:
    base = unit["base_availability"]
    value = base + rng.normal(0, AVAILABILITY_NOISE)
    if rng.random() < MAINTENANCE_EVENT_P:
        value -= rng.uniform(MAINTENANCE_DIP, 0.5)
    return round(float(np.clip(value, 0.25, 0.98)), 3)


def generate_equipment_fleet(rng_seed: int = 11) -> list[dict]:
    """Current-snapshot rows for the EQUIPMENT table."""
    rng: Generator = default_rng(rng_seed)
    fleet = []
    for unit in FLEET_SPEC:
        availability = _availability_for_day(unit, rng)
        downtime_hours = round((1 - availability) * SHIFT_HOURS, 1)
        operating_hours = round(SHIFT_HOURS - downtime_hours, 1)
        maintenance_hours = round(downtime_hours * rng.uniform(0.4, 0.8), 1)
        fleet.append(
            {
                "equipment_id": unit["equipment_id"],
                "mine_id": MINE_ID,
                "equipment_type": unit["equipment_type"],
                "current_zone_id": unit["zone_id"],
                "availability": availability,
                "operating_hours": operating_hours,
                "downtime_hours": downtime_hours,
                "maintenance_hours": maintenance_hours,
                "capacity": unit["capacity"],
            }
        )
    return fleet


def generate_status_history(
    fleet: list[dict],
    days: int = 90,
    rng_seed: int = 12,
) -> list[dict]:
    """Daily availability/downtime history per unit (for PHASE 15 training)."""
    rng: Generator = default_rng(rng_seed)
    today = date.today()
    records: list[dict] = []
    for unit in fleet:
        spec = next(s for s in FLEET_SPEC if s["equipment_id"] == unit["equipment_id"])
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            availability = _availability_for_day(spec, rng)
            downtime = round((1 - availability) * SHIFT_HOURS, 1)
            records.append(
                {
                    "equipment_id": unit["equipment_id"],
                    "date": d,
                    "availability": availability,
                    "operating_hours": round(SHIFT_HOURS - downtime, 1),
                    "downtime_hours": downtime,
                    "maintenance_hours": round(downtime * rng.uniform(0.3, 0.9), 1),
                }
            )
    return records
