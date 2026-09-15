"""Synthetic weather generator — Phase 8.

Two distinct generation modes:

1. HISTORICAL BASELINE — daily rainfall for all zones over a 12-month
   period with realistic monsoon seasonality (heavy Jun–Sep, dry otherwise)
   and zone-to-zone spatial variation (persistent per-zone factors + shared
   AOI-scale weather events, so adjacent zones are correlated but not
   identical).

2. DEMO SCENARIO TRIGGER — a clearly-flagged "current conditions" event:
   the PRD §44 at-risk zone gets a HIGH rainfall spike while the
   high-prospectivity zone stays favorable. This is the exact signal the
   Dynamic Scheduling module (Phase 18–21) reacts to.

rainfall_1d/7d/30d are always computed as rolling sums of the daily series
— internally consistent by construction, never independently randomized.

Designated zones (documented in docs/synthetic_data_assumptions.md §12):
- at-risk zone (rain spike): A1 (currently scheduled per PRD §44 narrative)
- favorable zone: B3 (high-prospectivity demo zone from Phase 5/6)
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from numpy.random import Generator, default_rng

AT_RISK_ZONE = "A1"
FAVORABLE_ZONE = "B3"

# --- monsoon seasonality (Balaghat belt: heavy Jun-Sep, dry otherwise) ---

MONSOON_DAILY_MEAN = 18.0  # mm/day during monsoon
DRY_DAILY_MEAN = 0.4  # mm/day outside monsoon
RAIN_EVENT_SHAPE = 1.5  # gamma shape for daily intensity
SPATIAL_NOISE = 0.25  # per-zone persistent factor spread


def _is_monsoon(d: date) -> bool:
    return d.month in (6, 7, 8, 9)


def _seasonal_mean(d: date) -> float:
    return MONSOON_DAILY_MEAN if _is_monsoon(d) else DRY_DAILY_MEAN


def _daily_series(
    zone_id: str,
    dates: list[date],
    factor: float,
    rng: Generator,
) -> dict[date, float]:
    """Daily rainfall for one zone: gamma draw scaled by season + zone factor."""
    series: dict[date, float] = {}
    for d in dates:
        mean = _seasonal_mean(d) * factor
        value = rng.gamma(shape=RAIN_EVENT_SHAPE, scale=mean / RAIN_EVENT_SHAPE)
        series[d] = round(float(value), 1)
    return series


def rolling_sum(series: dict[date, float], days: int, on_date: date) -> float:
    total = 0.0
    for i in range(days):
        total += series.get(on_date - timedelta(days=i), 0.0)
    return round(total, 1)


def generate_historical_baseline(
    zones: list,
    dates: list[date],
    rng_seed: int = 88,
) -> list[dict]:
    """12-month baseline: per-zone daily series + rolling aggregates."""
    rng: Generator = default_rng(rng_seed)
    factors = {zone.zone_id: float(rng.normal(1.0, SPATIAL_NOISE)) for zone in zones}

    records: list[dict] = []
    for zone in zones:
        zone_id = zone.zone_id
        daily = _daily_series(zone_id, dates, factors[zone_id], rng)
        for d in dates:
            records.append(
                {
                    "zone_id": zone_id,
                    "date": d,
                    "latitude": None,
                    "longitude": None,
                    "rainfall_1d": daily[d],
                    "rainfall_7d": rolling_sum(daily, 7, d),
                    "rainfall_30d": rolling_sum(daily, 30, d),
                    "scenario": "historical",
                }
            )
    return records


def generate_demo_scenario(
    zones: list,
    dates: list[date],
    spike_date: date | None = None,
    spike_1d: float = 110.0,
    rng_seed: int = 99,
) -> list[dict]:
    """Demo trigger: high rainfall on the at-risk zone, favorable elsewhere.

    - AT_RISK_ZONE (A1): spike_1d mm on spike_date, plus 45mm the day before
      and after (a 3-day storm) — heavy 7d accumulation crossing the
      risk-alert threshold.
    - FAVORABLE_ZONE (B3): dry conditions (trace rain only).
    - Other zones: light-to-moderate monsoon rain (no extreme signal).
    """
    rng: Generator = default_rng(rng_seed)
    trigger = spike_date or max(dates)
    if trigger not in dates:
        dates = sorted(set(dates) | {trigger})

    records: list[dict] = []
    for zone in zones:
        zone_id = zone.zone_id
        daily: dict[date, float] = {}
        for d in dates:
            if zone_id == AT_RISK_ZONE:
                if d == trigger:
                    daily[d] = spike_1d
                elif d in (trigger - timedelta(days=1), trigger + timedelta(days=1)):
                    daily[d] = 45.0
                else:
                    daily[d] = round(float(rng.gamma(2.0, 3.0)), 1)
            elif zone_id == FAVORABLE_ZONE:
                daily[d] = round(float(rng.gamma(0.3, 0.5)), 1)  # trace
            else:
                daily[d] = round(float(rng.gamma(2.0, 4.0)), 1)

        for d in dates:
            records.append(
                {
                    "zone_id": zone_id,
                    "date": d,
                    "latitude": None,
                    "longitude": None,
                    "rainfall_1d": daily[d],
                    "rainfall_7d": rolling_sum(daily, 7, d),
                    "rainfall_30d": rolling_sum(daily, 30, d),
                    "scenario": "demo",
                }
            )
    return records
