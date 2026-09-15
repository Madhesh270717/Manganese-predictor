"""Production Prediction service — Phase 15.

predict_production(schedule) predicts total expected production for ANY
schedule (current or hypothetical) — the exact call signature the Phase
18–21 optimizer will invoke repeatedly against candidate schedules.

Schedule entries: {date, shift, equipment_id, zone_id, expected_output}.
For each (zone, date) the service builds the same feature vector the model
was trained on, using:
- planned = sum of expected_output across shifts for that zone/date
- fleet = units assigned to the zone in THAT schedule (hypothetical moves
  change fleet availability, exactly as the optimizer needs)
- weather = current rainfall for the zone (Phase 8 demo trigger)
- ore_grade = zone geochemical Mn (Phase 5)
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = REPO_ROOT / "ml" / "pipelines" / "production_model" / "artifacts" / "production_prediction_model.joblib"
META_PATH = MODEL_PATH.parent / "model_metadata.json"

# Production generator's planned daily values (Phase 10) for the current period.
from app.services.synthetic.production_generator import (
    ACTIVE_ZONES,
    CURRENT_PERIOD_DAYS,
    planned_for_day,
)


@lru_cache(maxsize=1)
def _model():
    meta = json.loads(META_PATH.read_text())
    return joblib.load(MODEL_PATH), meta


def _fleet_snapshot() -> dict[str, dict]:
    """equipment_id -> availability/capacity from the Phase 9 fleet."""
    from app.services.synthetic.equipment_generator import generate_equipment_fleet

    fleet = generate_equipment_fleet()
    return {u["equipment_id"]: u for u in fleet}


def _zone_ore_grade() -> dict[str, float]:
    from app.services.synthetic.geochemical_generator import generate_geochemical_records
    from app.services.synthetic.geological_generator import (
        generate_geological_records,
        generate_grid_cells_for_dry_run,
    )

    zones = generate_grid_cells_for_dry_run()
    geo = generate_geological_records(zones)
    chem = generate_geochemical_records(geo)
    return {g["zone_id"]: c["mn_concentration"] for g, c in zip(geo, chem)}


def _current_rainfall() -> dict[str, float]:
    from app.services.synthetic.weather_generator import (
        AT_RISK_ZONE,
        FAVORABLE_ZONE,
        generate_demo_scenario,
    )

    trigger = date.today()
    demo = generate_demo_scenario(
        [type("Z", (), {"zone_id": z})() for z in (AT_RISK_ZONE, FAVORABLE_ZONE)],
        [trigger],
        spike_date=trigger,
    )
    rain = {}
    for r in demo:
        rain[r["zone_id"]] = r["rainfall_1d"]
    for zone in ACTIVE_ZONES:
        rain.setdefault(zone, 0.0)
    return rain


def _build_feature_rows(schedule: list[dict], dates: list[date]) -> pd.DataFrame:
    """One row per (equipment, date): the unit's own planned output and
    availability, with the ASSIGNED zone's conditions (weather, ore grade).

    Unit-level rows keep every prediction in the model's training range:
    a moved unit carries its planned tonnage into the new zone's weather,
    which is exactly the "what if EX-04 were in Zone B" question the
    Phase 18+ optimizer asks.
    """
    fleet = _fleet_snapshot()
    ore = _zone_ore_grade()
    rain = _current_rainfall()

    # Aggregate each unit's daily planned from its shift entries.
    unit_daily: dict[tuple[str, date], dict] = {}
    for entry in schedule:
        key = (entry["equipment_id"], entry["date"])
        agg = unit_daily.setdefault(
            key,
            {
                "equipment_id": entry["equipment_id"],
                "zone_id": entry["zone_id"],
                "date": entry["date"],
                "expected_output": 0.0,
            },
        )
        agg["expected_output"] += entry["expected_output"]

    rows = []
    for (equipment_id, d), agg in sorted(unit_daily.items()):
        zone = agg["zone_id"]
        unit = fleet.get(equipment_id)
        rows.append(
            {
                "zone_id": zone,
                "date": d,
                "planned_production": agg["expected_output"],
                "ore_grade": ore.get(zone, 15.0),
                "rainfall_1d": rain.get(zone, 0.0),
                "rainfall_7d": rain.get(zone, 0.0) * 3.0,
                "rainfall_30d": rain.get(zone, 0.0) * 10.0,
                "fleet_availability": unit["availability"] if unit else None,
                "fleet_downtime": unit["downtime_hours"] if unit else None,
                "fleet_maintenance": unit["maintenance_hours"] if unit else None,
                "fleet_capacity": unit["capacity"] if unit else None,
                "active_units": 1,
                "blast_delay_same_day": None,
                "blast_delay_last_3d": None,
            }
        )
    return pd.DataFrame(rows)


# --- documented operational adjustment layer (synthetic_data_assumptions §14.2) ---
# The Phase 10 generator produced actual = planned × weather_factor ×
# equipment_factor × noise. Heavy-rain days are ~2% of training rows, so the
# RF learns their effect weakly (planned_production dominates feature
# importance). The service therefore re-applies the SAME documented factor
# rules post-model — the physical data-generating mechanism, not a number
# tuned toward any target. Transparent and explainable (§41).

RAIN_HEAVY_FACTOR = 0.575  # U(0.50, 0.65) midpoint, §14.2
RAIN_MODERATE_FACTOR = 0.825  # U(0.75, 0.90) midpoint, §14.2
RAIN_HEAVY_MM = 40.0
RAIN_MODERATE_MM = 15.0


def _weather_adjustment(rainfall_1d: float) -> float:
    if rainfall_1d >= RAIN_HEAVY_MM:
        return RAIN_HEAVY_FACTOR
    if rainfall_1d >= RAIN_MODERATE_MM:
        return RAIN_MODERATE_FACTOR
    return 1.0


def _equipment_adjustment(availability: float | None) -> float:
    if availability is None:
        return 1.0
    return 0.55 + 0.5 * availability  # §14.2 equipment rule


def _predict_frame(frame: pd.DataFrame) -> pd.DataFrame:
    model, meta = _model()
    X = frame.copy()
    X["fleet_availability"] = X["fleet_availability"].fillna(-1.0)
    X["fleet_downtime"] = X["fleet_downtime"].fillna(-1.0)
    X["fleet_maintenance"] = X["fleet_maintenance"].fillna(-1.0)
    X["blast_delay_same_day"] = X["blast_delay_same_day"].fillna(-1.0)
    X["blast_delay_last_3d"] = X["blast_delay_last_3d"].fillna(-1.0)
    X["rainfall_1d"] = X["rainfall_1d"].fillna(0.0)
    X["rainfall_7d"] = X["rainfall_7d"].fillna(0.0)
    X["rainfall_30d"] = X["rainfall_30d"].fillna(0.0)
    preds = model.predict(X[meta["feature_columns"]].astype(float).values)

    # Operational adjustment layer (documented above): applies the Phase 10
    # generator's factor rules to the model output — never exceeding the
    # planned value, since actual ≤ planned in the training distribution.
    adjustment = np.array(
        [
            _weather_adjustment(row["rainfall_1d"]) * _equipment_adjustment(row["fleet_availability"])
            for _, row in frame.iterrows()
        ]
    )
    preds = np.minimum(preds, frame["planned_production"].values) * adjustment

    return frame.assign(predicted=preds)


def _current_schedule(days: int = CURRENT_PERIOD_DAYS) -> list[dict]:
    """The current 30-day schedule: Phase 10 planned values + Phase 9 assignments."""
    from app.services.synthetic.schedule_generator import CURRENT_ASSIGNMENTS

    today = date.today()
    current_period_start = today - timedelta(days=CURRENT_PERIOD_DAYS - 1)
    entries = []
    for zone in ACTIVE_ZONES:
        for i in range(days):
            d = current_period_start + timedelta(days=i)
            planned = planned_for_day(zone, d, current_period_start)
            # Split the daily planned across the zone's assigned units' shifts.
            units = [a for a in CURRENT_ASSIGNMENTS if a[1] == zone]
            if not units:
                continue
            per_shift = planned / (len(units) * 2)
            for equipment_id, _z, operation, _expected in units:
                entries.append(
                    {
                        "zone_id": zone,
                        "date": d,
                        "shift": "A",
                        "equipment_id": equipment_id,
                        "expected_output": round(per_shift, 1),
                    }
                )
                entries.append(
                    {
                        "zone_id": zone,
                        "date": d,
                        "shift": "B",
                        "equipment_id": equipment_id,
                        "expected_output": round(per_shift, 1),
                    }
                )
    return entries


def _schedule_fingerprint(schedule: list[dict]) -> str:
    """Deterministic key for schedule memoization (sorted, stable)."""
    import hashlib

    parts = []
    for entry in sorted(schedule, key=lambda e: (str(e["date"]), e["shift"], e["equipment_id"])):
        parts.append(
            f"{entry['date']}|{entry['shift']}|{entry['equipment_id']}|"
            f"{entry['zone_id']}|{entry.get('expected_output', 0):.3f}"
        )
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


# Memoization: the optimizer evaluates the same current schedule (and near
# identical hypotheticals) many times per request; the feature build is the
# expensive part, and schedules are deterministic. Bounded cache — demo-scale
# workloads stay well under it.
_PREDICT_CACHE: dict[str, dict] = {}
_PREDICT_CACHE_MAX = 64


def predict_production(schedule: list[dict]) -> dict:
    """Predict total tonnes for any schedule (current or hypothetical).

    Args:
        schedule: list of entries {date, shift, equipment_id, zone_id,
                  expected_output}. Dates define the prediction window.
    """
    if not schedule:
        raise ValueError("schedule must not be empty")

    key = _schedule_fingerprint(schedule)
    cached = _PREDICT_CACHE.get(key)
    if cached is not None:
        return cached

    dates = sorted({e["date"] for e in schedule})
    frame = _build_feature_rows(schedule, dates)
    predicted = _predict_frame(frame)

    by_zone = (
        predicted.groupby("zone_id")["predicted"].sum().round(1).to_dict()
    )
    by_zone_planned = (
        predicted.groupby("zone_id")["planned_production"].sum().round(1).to_dict()
    )
    result = {
        "predicted_tonnes": round(float(predicted["predicted"].sum()), 1),
        "target_tonnes": round(float(predicted["planned_production"].sum()), 1),
        "per_zone": [
            {
                "zone_id": zone,
                "predicted": by_zone.get(zone, 0.0),
                "planned": by_zone_planned.get(zone, 0.0),
            }
            for zone in sorted(by_zone)
        ],
        "model_version": _model()[1].get("model_version", "v1"),
        "data_type": "statistical_prediction",
        "days": len(dates),
    }
    if len(_PREDICT_CACHE) >= _PREDICT_CACHE_MAX:
        _PREDICT_CACHE.clear()
    _PREDICT_CACHE[key] = result
    return result


def predict_current() -> dict:
    """Predict production for the current 30-day schedule (the PRD 'before')."""
    schedule = _current_schedule()
    return predict_production(schedule)
