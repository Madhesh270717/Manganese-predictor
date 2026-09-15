"""Synthetic blasting schedule generator — Phase 9.

Generates blast records tied to zones, concentrating on the
high-prospectivity cluster (blasting precedes excavation there) and the
at-risk zone A1 (where the Phase 8 rainfall spike delays blasting).

Delay model (documented in docs/synthetic_data_assumptions.md §13):
- Most blasts run on/near schedule (delay ~N(0, 0.4) hours).
- A meaningful subset is delayed; A1's delays are larger and explicitly
  rain-correlated: delay_hours scales with rainfall_1d on the planned date.
- Designed so aggregate delay attribution can justify the PRD §16
  "Blasting delays 20%" shortfall contributor example.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
from numpy.random import Generator, default_rng

from app.services.synthetic.geological_generator import HIGH_PROSPECTIVITY_ZONES
from app.services.synthetic.weather_generator import AT_RISK_ZONE

# Blast counts per zone per month (cluster + at-risk zone get more).
ZONE_BLAST_COUNTS: dict[str, int] = {"B2": 3, "B3": 4, "C2": 3, "C3": 3, "A1": 3}

RAIN_DELAY_FACTOR = 0.05  # hours of delay per mm of rainfall_1d
BASE_DELAY_NOISE = 0.4  # hours (on/near schedule when no rain)


def generate_blasting_records(
    zones: list,
    weather_daily: dict[str, dict[date, float]] | None = None,
    n_weeks: int = 12,
    rng_seed: int = 13,
) -> list[dict]:
    """Blast records over the last n_weeks for blast-active zones.

    Args:
        zones: Zone ORM rows (zone_id + geometry).
        weather_daily: {zone_id: {date: rainfall_1d}} from Phase 8; when
            provided, delays for the at-risk zone scale with rain.
        n_weeks: number of weeks back from today.
        rng_seed: fixed seed.
    """
    rng: Generator = default_rng(rng_seed)
    today = datetime.now(timezone.utc).date()
    weather_daily = weather_daily or {}

    records: list[dict] = []
    for zone in zones:
        zone_id = zone.zone_id
        count = ZONE_BLAST_COUNTS.get(zone_id)
        if count is None:
            continue

        zone_weather = weather_daily.get(zone_id, {})
        for i in range(1, count + 1):
            # Spread blasts across the window deterministically per zone.
            day_offset = (n_weeks * 7 * i) // (count + 1)
            planned_date = today - timedelta(days=day_offset)
            planned_time = datetime(
                planned_date.year, planned_date.month, planned_date.day,
                8, 0, tzinfo=timezone.utc,
            )

            rain_mm = zone_weather.get(planned_date, 0.0)
            if zone_id == AT_RISK_ZONE and rain_mm > 0:
                # Rain-correlated delay: heavy rain -> hours of delay.
                delay = rng.normal(rain_mm * RAIN_DELAY_FACTOR, 0.3)
            else:
                delay = rng.normal(0, BASE_DELAY_NOISE)
            delay = max(0.0, float(delay))

            records.append(
                {
                    "blast_id": f"SYN-BL-{zone_id}-{i:02d}",
                    "zone_id": zone_id,
                    "planned_time": planned_time,
                    "actual_time": planned_time + timedelta(hours=delay),
                    "delay_hours": round(delay, 2),
                }
            )
    return records
