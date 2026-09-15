"""Mineability service — Phase 14.

Computes the mineability score LIVE on every request: weather (current
rainfall) and equipment availability are queried fresh each time, never
cached. This is what makes Dynamic Scheduling (Phase 18+) possible — the
optimizer must see score changes the moment conditions change.

Design choice (documented): static components (prospectivity, resource,
terrain/access) come from the feature/terrain data; dynamic components
(weather, equipment) are queried per call via the synthetic fallback when
no database is available.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from ml.pipelines.mineability_model.score import composite_score

# DB availability is probed once per process: after the first failed
# connection attempt, all dynamic lookups use the synthetic fallback
# (fast-fail — otherwise every zone's lookups pay the connect timeout).
_DB_UNAVAILABLE = False


def _db_session():
    """Return a SessionLocal context manager, or None if DB is known down."""
    global _DB_UNAVAILABLE
    if _DB_UNAVAILABLE:
        return None
    try:
        from app.core.database import SessionLocal

        return SessionLocal
    except Exception:
        _DB_UNAVAILABLE = True
        return None


@lru_cache(maxsize=1)
def _terrain_by_zone() -> dict[str, dict]:
    """Terrain/access per zone — DB first, synthetic fallback (cached)."""
    global _DB_UNAVAILABLE
    SessionLocal = _db_session()
    if SessionLocal is not None:
        try:
            from sqlalchemy import select

            from app.models import ZoneTerrainAccess

            with SessionLocal() as session:
                rows = session.execute(
                    select(ZoneTerrainAccess.zone_id, ZoneTerrainAccess.slope_degrees,
                           ZoneTerrainAccess.accessibility_rating, ZoneTerrainAccess.haul_distance_km,
                           ZoneTerrainAccess.road_condition)
                ).all()
            if rows:
                return {
                    z: {
                        "slope_degrees": s,
                        "accessibility": a,
                        "haul_km": h,
                        "road_condition": r,
                    }
                    for z, s, a, h, r in rows
                }
        except Exception:
            _DB_UNAVAILABLE = True

    from app.services.synthetic.geological_generator import generate_grid_cells_for_dry_run
    from app.services.synthetic.terrain_generator import generate_terrain_records

    fake = generate_grid_cells_for_dry_run()
    return {
        r["zone_id"]: {
            "slope_degrees": r["slope_degrees"],
            "accessibility": r["accessibility_rating"],
            "haul_km": r["haul_distance_km"],
            "road_condition": r["road_condition"],
        }
        for r in generate_terrain_records(fake)
    }


def _current_weather(zone_id: str) -> float | None:
    """rainfall_1d for today (DB) or the demo-trigger value (fallback).

    Uses the batched per-zone snapshot so repeated calls inside the
    optimization engine share one DB round-trip (live remote DBs: Supabase).
    """
    return _weather_by_zone().get(zone_id)


def _current_fleet_availability(zone_id: str) -> float | None:
    """Mean availability of equipment currently assigned to the zone."""
    return _fleet_availability_by_zone().get(zone_id)


@lru_cache(maxsize=1)
def _weather_by_zone() -> dict[str, float]:
    """rainfall_1d for today for ALL zones, one query (cached per process)."""
    global _DB_UNAVAILABLE
    SessionLocal = _db_session()
    if SessionLocal is not None:
        try:
            from sqlalchemy import select

            from app.models import Weather

            with SessionLocal() as session:
                rows = session.execute(
                    select(Weather.zone_id, Weather.rainfall_1d).where(
                        Weather.date == date.today()
                    )
                ).all()
            if rows:
                return {z: float(r) for z, r in rows if r is not None}
        except Exception:
            _DB_UNAVAILABLE = True

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
    return {r["zone_id"]: r["rainfall_1d"] for r in demo}


@lru_cache(maxsize=1)
def _fleet_availability_by_zone() -> dict[str, float]:
    """Mean fleet availability per zone, one query (cached per process)."""
    global _DB_UNAVAILABLE
    SessionLocal = _db_session()
    if SessionLocal is not None:
        try:
            from sqlalchemy import select

            from app.models import Equipment

            with SessionLocal() as session:
                rows = session.execute(
                    select(Equipment.current_zone_id, Equipment.availability)
                ).all()
            grouped: dict[str, list[float]] = {}
            for zone_id, avail in rows:
                if zone_id is None or avail is None:
                    continue
                grouped.setdefault(zone_id, []).append(float(avail))
            if grouped:
                return {
                    z: sum(values) / len(values) for z, values in grouped.items()
                }
        except Exception:
            _DB_UNAVAILABLE = True

    from app.services.synthetic.equipment_generator import generate_equipment_fleet

    fleet = generate_equipment_fleet()
    grouped: dict[str, list[float]] = {}
    for u in fleet:
        grouped.setdefault(u["current_zone_id"], []).append(u["availability"])
    return {z: sum(values) / len(values) for z, values in grouped.items()}


def _prospectivity(zone_id: str) -> float | None:
    from app.services.reserve_model_service import get_prospectivity

    result = get_prospectivity(zone_id)
    return result["prospectivity_score"] if result else None


def _resource_confidence(zone_id: str) -> str:
    from app.services.resource_estimation_service import get_resource_estimate

    result = get_resource_estimate(zone_id)
    return result["confidence_level"] if result else "NOT_ESTIMATED"


def get_mineability(zone_id: str) -> dict | None:
    """Full component breakdown + composite score for one zone (LIVE)."""
    terrain = _terrain_by_zone().get(zone_id)
    prospectivity = _prospectivity(zone_id)
    if terrain is None or prospectivity is None:
        return None

    result = composite_score(
        prospectivity=prospectivity,
        resource_confidence=_resource_confidence(zone_id),
        slope_degrees=terrain["slope_degrees"],
        accessibility=terrain["accessibility"],
        haul_km=terrain["haul_km"],
        road_condition=terrain["road_condition"],
        rainfall_1d=_current_weather(zone_id),
        fleet_availability=_current_fleet_availability(zone_id),
    )
    return {
        "zone_id": zone_id,
        "prospectivity": prospectivity,
        "resource_confidence": _resource_confidence(zone_id),
        "terrain": terrain,
        "current_rainfall_1d": _current_weather(zone_id),
        "fleet_availability": _current_fleet_availability(zone_id),
        **result,
        "dynamic": True,
        "computed_at": date.today().isoformat(),
    }


def get_all_mineability() -> dict:
    """All-zone payload, sorted by score desc."""
    zones = sorted(
        (get_mineability(z) for z in _terrain_by_zone()),
        key=lambda z: z["mineability_score"] if z else -1,
        reverse=True,
    )
    zones = [z for z in zones if z is not None]
    return {"count": len(zones), "zones": zones}
