"""Production feature builder — Phase 11.

One row per (zone_id, date) with strictly AS-OF joins — no future leakage:

- equipment: mean fleet availability/downtime for the zone's units as of
  that date (most recent history row at or before the date)
- weather: that date's rainfall_1d/7d/30d
- blasting: delay_hours if a blast occurred on that date in that zone,
  plus a trailing 3-day max delay
- target: actual_production for that date

Pure transformation functions: the caller supplies the source tables.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _build_equipment_daily(equipment: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """Daily per-zone fleet aggregates from equipment snapshot + history.

    equipment: [equipment_id, current_zone_id, capacity]
    history:   [equipment_id, date, availability, downtime_hours,
                maintenance_hours]
    Returns: [zone_id, date, fleet_availability, fleet_downtime,
              fleet_maintenance, fleet_capacity, active_units]
    """
    unit_zone = equipment[["equipment_id", "current_zone_id"]].drop_duplicates()
    merged = history.merge(unit_zone, on="equipment_id", how="left")
    merged = merged.dropna(subset=["current_zone_id"])

    daily = (
        merged.groupby(["current_zone_id", "date"])
        .agg(
            fleet_availability=("availability", "mean"),
            fleet_downtime=("downtime_hours", "sum"),
            fleet_maintenance=("maintenance_hours", "sum"),
            active_units=("equipment_id", "count"),
        )
        .reset_index()
        .rename(columns={"current_zone_id": "zone_id"})
    )

    cap = (
        equipment.groupby("current_zone_id")["capacity"]
        .sum()
        .reset_index()
        .rename(columns={"current_zone_id": "zone_id", "capacity": "fleet_capacity"})
    )
    daily = daily.merge(cap, on="zone_id", how="left")
    return daily


def build_production_features(
    production: pd.DataFrame,
    equipment: pd.DataFrame,
    equipment_history: pd.DataFrame,
    weather: pd.DataFrame,
    blasting: pd.DataFrame,
) -> pd.DataFrame:
    """Join production (target) with as-of features for each (zone, date).

    production: [date, mine_id, zone_id, planned_production,
                 actual_production, ore_grade]
    weather:    [zone_id, date, rainfall_1d, rainfall_7d, rainfall_30d]
    blasting:   [zone_id, date, delay_hours] (blast date)
    """
    features = production.copy()
    features["date"] = pd.to_datetime(features["date"])

    # weather: exact-date join (no leakage — rainfall is known same-day).
    weather = weather.copy()
    weather["date"] = pd.to_datetime(weather["date"])
    weather_cols = ["zone_id", "date", "rainfall_1d", "rainfall_7d", "rainfall_30d"]
    features = features.merge(weather[weather_cols], on=["zone_id", "date"], how="left")

    # equipment: as-of join (most recent history row at or before date).
    daily_eq = _build_equipment_daily(equipment, equipment_history).sort_values("date")
    daily_eq["date"] = pd.to_datetime(daily_eq["date"])
    features = features.sort_values("date")
    features = pd.merge_asof(
        features,
        daily_eq,
        on="date",
        by="zone_id",
        direction="backward",
        allow_exact_matches=True,
    )

    # blasting: same-day delay + trailing 3-day max delay (recent disruption).
    blast = blasting[["zone_id", "delay_hours"]].copy()
    if "date" in blasting.columns:
        blast["date"] = pd.to_datetime(blasting["date"])
    else:
        blast["date"] = pd.to_datetime(blasting["planned_time"]).dt.tz_localize(None).dt.normalize()
    blast["date"] = pd.to_datetime(blast["date"])
    # Multiple blasts per zone-day: keep the worst (max) delay — one row per (zone, date).
    blast = blast.groupby(["zone_id", "date"], as_index=False)["delay_hours"].max()
    features = features.merge(blast, on=["zone_id", "date"], how="left")
    features = features.rename(columns={"delay_hours": "blast_delay_same_day"})

    blast["date_plus"] = blast["date"] + pd.Timedelta(days=3)
    rolling_delay = (
        blast.rename(columns={"date": "blast_date", "date_plus": "date"})
        .groupby(["zone_id", "date"])["delay_hours"]
        .max()
        .reset_index()
        .rename(columns={"delay_hours": "blast_delay_last_3d"})
    )
    features = features.merge(rolling_delay, on=["zone_id", "date"], how="left")

    # Missingness flags for the model (Phase 15) — never silent zero-fill.
    features["has_weather"] = features["rainfall_1d"].notna()
    features["has_equipment"] = features["fleet_availability"].notna()
    features["has_blast_same_day"] = features["blast_delay_same_day"].notna()

    # Feature order: target last.
    cols = [c for c in features.columns if c != "actual_production"] + ["actual_production"]
    return features[cols]
