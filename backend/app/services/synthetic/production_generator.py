"""Synthetic production history generator — Phase 10.

Daily planned vs actual production for the active mining zones over the
last 12 months, with REALISTIC, LEARNABLE relationships to the upstream
factors already seeded (this is the training signal for Phase 15):

- rainfall (Phase 8): heavy rain scales actual output down
- equipment availability (Phase 9): low fleet availability reduces output
- blasting delays (Phase 9): delayed blasts cut the day's output
- plus per-day noise with occasional over-target days (not a flat pattern)

Current period (last 30 days): planned values are FIXED per zone so the
total equals the PRD §13/§44 demo target of 82,000 t:

    B3 24,000 + C3 19,500 + B2 16,500 + C2 13,800 + A1 8,200 = 82,000 t

The ~74,600 t prediction is NOT fabricated here — that is the Phase 15
model's job. This phase only sets up realistic planned targets + historical
training data.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from numpy.random import Generator, default_rng

ACTIVE_ZONES: tuple[str, ...] = ("A1", "B2", "B3", "C2", "C3")
CURRENT_PERIOD_DAYS = 30
MINE_ID = "MOIL-BALAGHAT"

# Daily planned production (tonnes) per zone in the current period.
PLANNED_DAILY: dict[str, float] = {
    "B3": 800.0,   # 24,000 over 30 days
    "C3": 650.0,   # 19,500
    "B2": 550.0,   # 16,500
    "C2": 460.0,   # 13,800
    # A1: 8,200 total via a 273/274 pattern (see planned_for_day).
}

RAIN_HEAVY_MM = 40.0
RAIN_MODERATE_MM = 15.0
GRADE_NOISE = 2.0
GRADE_CLIP = (10.0, 48.0)
NOISE_SIGMA = 0.06
FACTOR_CLIP = (0.5, 1.2)


def planned_for_day(zone_id: str, d: date, current_period_start: date) -> float:
    """Planned tonnes for one zone on one day.

    A1 alternates 273/274 t so any 30-day window totals exactly 8,200 t
    (30 days = 10 triplets, one 274-day per triplet).
    """
    if zone_id == "A1":
        if d >= current_period_start:
            return 274.0 if (d.toordinal() % 3 == 0) else 273.0
        return 273.0
    return PLANNED_DAILY[zone_id]


def generate_production_records(
    dates: list[date],
    zone_mn: dict[str, float],
    weather_daily: dict[str, dict[date, float]] | None = None,
    equipment_availability: dict[str, dict[date, float]] | None = None,
    blasting_delays: dict[str, dict[date, float]] | None = None,
    rng_seed: int = 21,
) -> list[dict]:
    """Generate PRODUCTION rows for active zones across `dates`.

    Args:
        dates: daily dates (typically last 365 days).
        zone_mn: zone_id -> Phase 5 geochemical mn_concentration.
        weather_daily: {zone_id: {date: rainfall_1d}} from Phase 8.
        equipment_availability: {zone_id: {date: mean fleet availability}}
            from Phase 9 history.
        blasting_delays: {zone_id: {date: delay_hours}} from Phase 9.
        rng_seed: fixed seed.
    """
    rng: Generator = default_rng(rng_seed)
    weather_daily = weather_daily or {}
    equipment_availability = equipment_availability or {}
    blasting_delays = blasting_delays or {}

    current_period_start = max(dates) - timedelta(days=CURRENT_PERIOD_DAYS - 1)

    records: list[dict] = []
    for zone_id in ACTIVE_ZONES:
        zone_weather = weather_daily.get(zone_id, {})
        zone_avail = equipment_availability.get(zone_id, {})
        zone_delays = blasting_delays.get(zone_id, {})
        mn = float(zone_mn.get(zone_id, 15.0))

        for d in dates:
            planned = planned_for_day(zone_id, d, current_period_start)

            factor = 1.0
            rain = zone_weather.get(d, 0.0)
            if rain >= RAIN_HEAVY_MM:
                factor *= float(rng.uniform(0.50, 0.65))
            elif rain >= RAIN_MODERATE_MM:
                factor *= float(rng.uniform(0.75, 0.90))

            avail = zone_avail.get(d)
            if avail is not None:
                factor *= 0.55 + 0.5 * avail

            if zone_delays.get(d, 0.0) > 3.0:
                factor *= 0.75

            factor *= float(rng.normal(1.0, NOISE_SIGMA))
            factor = float(np.clip(factor, *FACTOR_CLIP))

            records.append(
                {
                    "date": d,
                    "mine_id": MINE_ID,
                    "zone_id": zone_id,
                    "planned_production": round(planned, 1),
                    "actual_production": round(planned * factor, 1),
                    "ore_grade": round(float(np.clip(mn + rng.normal(0, GRADE_NOISE), *GRADE_CLIP)), 2),
                }
            )
    return records


def current_period_planned_total(dates: list[date]) -> float:
    """Sum planned production for the current 30-day period (expects 82,000)."""
    current_period_start = max(dates) - timedelta(days=CURRENT_PERIOD_DAYS - 1)
    total = 0.0
    for zone_id in ACTIVE_ZONES:
        for d in dates:
            if d >= current_period_start:
                total += planned_for_day(zone_id, d, current_period_start)
    return round(total, 1)
