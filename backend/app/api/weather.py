"""Weather API — time series, current conditions, risk alerts."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import DataSourceMetadata, Weather, Zone
from app.services.weather_service import latest_weather, scan_risk_alerts

router = APIRouter(tags=["weather"])


def _confidence_payload(session: Session, dataset_name: str) -> dict:
    try:
        row = session.scalar(
            select(DataSourceMetadata).where(DataSourceMetadata.dataset_name == dataset_name)
        )
    except Exception:
        row = None
    if row is None:
        return {"dataset": dataset_name, "confidence": "UNKNOWN"}
    return {
        "dataset": row.dataset_name,
        "source_type": row.source_type.value,
        "confidence_level": row.confidence_level.value,
        "source_name": row.source_name,
    }


def _weather_payload(row: Weather) -> dict:
    return {
        "zone_id": row.zone_id,
        "date": row.date.isoformat(),
        "rainfall_1d": row.rainfall_1d,
        "rainfall_7d": row.rainfall_7d,
        "rainfall_30d": row.rainfall_30d,
        "scenario": row.scenario,
    }


@router.get("/zones/{zone_id}/weather")
def get_zone_weather(
    zone_id: str,
    db: Session = Depends(get_db),
    start: date | None = Query(None, description="Start date (inclusive)"),
    end: date | None = Query(None, description="End date (inclusive)"),
) -> dict:
    """Weather time series for a zone, optionally filtered by date range."""
    from app.api.zones import _resolve_zone

    if _resolve_zone(db, zone_id) is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    try:
        stmt = select(Weather).where(Weather.zone_id == zone_id)
        if start is not None:
            stmt = stmt.where(Weather.date >= start)
        if end is not None:
            stmt = stmt.where(Weather.date <= end)
        rows = list(db.scalars(stmt.order_by(Weather.date)).all())
    except Exception:
        # Synthetic fallback (DB-less demo machines): demo trigger + baseline.
        from datetime import timedelta

        from app.services.synthetic.weather_generator import (
            generate_demo_scenario,
            generate_historical_baseline,
        )

        class _Z:
            def __init__(self, zone_id):
                self.zone_id = zone_id

        today = date.today()
        dates = [today - timedelta(days=i) for i in range(13, -1, -1)]
        demo = generate_demo_scenario([_Z(zone_id)], dates, spike_date=today)
        baseline = generate_historical_baseline([_Z(zone_id)], dates[:7])

        class _R:
            def __init__(self, row):
                for key, value in row.items():
                    setattr(self, key, value)

        rows = [_R(r) for r in demo + baseline]
        rows.sort(key=lambda r: r.date)

    return {
        "zone_id": zone_id,
        "count": len(rows),
        "series": [_weather_payload(r) for r in rows],
        "confidence": _confidence_payload(db, "Weather"),
    }


@router.get("/zones/{zone_id}/weather/current")
def get_zone_weather_current(zone_id: str, db: Session = Depends(get_db)) -> dict:
    """Current conditions with latest-available fallback (PRD §41)."""
    from app.api.zones import _resolve_zone

    if _resolve_zone(db, zone_id) is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    try:
        result = latest_weather(db, zone_id)
    except Exception:
        # Synthetic fallback (DB-less demo machines).
        from app.services.synthetic.weather_generator import (
            generate_demo_scenario,
        )

        class _Z:
            def __init__(self, zone_id):
                self.zone_id = zone_id

        today = date.today()
        demo = generate_demo_scenario([_Z(zone_id)], [today], spike_date=today)
        row = next((r for r in demo if r["zone_id"] == zone_id), None)
        if row is None:
            result = {
                "zone_id": zone_id,
                "date": today.isoformat(),
                "rainfall_1d": None,
                "rainfall_7d": None,
                "rainfall_30d": None,
                "is_stale": True,
                "data_age_days": None,
                "note": "no weather data available for this zone",
            }
        else:
            result = {
                "zone_id": zone_id,
                "date": row["date"].isoformat(),
                "rainfall_1d": row["rainfall_1d"],
                "rainfall_7d": row["rainfall_7d"],
                "rainfall_30d": row["rainfall_30d"],
                "is_stale": False,
                "data_age_days": 0,
                "source": "synthetic-fallback",
            }
    result["confidence"] = _confidence_payload(db, "Weather")
    return result


@router.get("/weather/risk-alert")
def weather_risk_alert(db: Session = Depends(get_db)) -> dict:
    """Scan all zones for high-rainfall flags (threshold-based).

    DB-first with synthetic fallback: on DB-less demo machines the alert
    scan uses the Phase 8 demo-scenario generator so the screen never 500s.
    """
    try:
        return scan_risk_alerts(db)
    except Exception:
        # Fallback: derive the same alert payload from the synthetic demo
        # trigger (A1 rainfall spike) — the Phase 8 threshold rule.
        from app.services.synthetic.weather_generator import (
            AT_RISK_ZONE,
            FAVORABLE_ZONE,
            generate_demo_scenario,
        )

        class _Z:
            def __init__(self, zone_id):
                self.zone_id = zone_id

        trigger = date.today()
        demo = generate_demo_scenario(
            [_Z(z) for z in (AT_RISK_ZONE, FAVORABLE_ZONE)],
            [trigger],
            spike_date=trigger,
        )
        alerts = []
        for row in demo:
            if row["rainfall_1d"] >= 60.0 or row["rainfall_7d"] >= 150.0:
                alerts.append(
                    {
                        "zone_id": row["zone_id"],
                        "date": row["date"].isoformat(),
                        "rainfall_1d": row["rainfall_1d"],
                        "rainfall_7d": row["rainfall_7d"],
                        "trigger": "rainfall_1d" if row["rainfall_1d"] >= 60.0 else "rainfall_7d",
                    }
                )
        return {
            "date": trigger.isoformat(),
            "thresholds": {"rainfall_1d": 60.0, "rainfall_7d": 150.0},
            "alerts": alerts,
            "source": "synthetic-fallback",
        }
