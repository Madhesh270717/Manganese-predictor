"""Weather service — Phase 8.

Latest-available fallback (PRD §41 Reliability): if no weather row exists
for "today" (or the requested date), return the last known reading with a
staleness flag instead of failing. Production Intelligence (Phase 16) and
the Dynamic Scheduling optimizer (Phase 18+) will reuse this.

Risk-alert: threshold-based scan across zones for high rainfall_1d/7d —
the precursor signal for Phase 18's re-optimization trigger. No scoring
logic yet, just flags.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Weather

# Risk thresholds (mm/day) — documented in synthetic_data_assumptions.md §12.
RISK_RAINFALL_1D = 60.0
RISK_RAINFALL_7D = 150.0


def latest_weather(session: Session, zone_id: str, on_date: date | None = None) -> dict:
    """Most recent weather reading for a zone, with staleness fallback.

    If no row exists for on_date (default: today), the latest available row
    is returned with is_stale=True and data_age_days set. If the zone has no
    rows at all, returns a not_found payload.
    """
    on_date = on_date or date.today()

    row = session.scalar(
        select(Weather)
        .where(Weather.zone_id == zone_id, Weather.date == on_date)
        .limit(1)
    )
    if row is not None:
        return {
            "zone_id": zone_id,
            "date": row.date.isoformat(),
            "rainfall_1d": row.rainfall_1d,
            "rainfall_7d": row.rainfall_7d,
            "rainfall_30d": row.rainfall_30d,
            "is_stale": False,
            "data_age_days": 0,
        }

    last = session.scalar(
        select(Weather)
        .where(Weather.zone_id == zone_id, Weather.date <= on_date)
        .order_by(Weather.date.desc())
        .limit(1)
    )
    if last is None:
        return {
            "zone_id": zone_id,
            "date": on_date.isoformat(),
            "rainfall_1d": None,
            "rainfall_7d": None,
            "rainfall_30d": None,
            "is_stale": True,
            "data_age_days": None,
            "note": "no weather data available for this zone",
        }

    age = (on_date - last.date).days
    return {
        "zone_id": zone_id,
        "date": last.date.isoformat(),
        "rainfall_1d": last.rainfall_1d,
        "rainfall_7d": last.rainfall_7d,
        "rainfall_30d": last.rainfall_30d,
        "is_stale": True,
        "data_age_days": age,
    }


def scan_risk_alerts(session: Session, on_date: date | None = None) -> dict:
    """Flag zones currently showing high rainfall (threshold-based)."""
    on_date = on_date or date.today()

    rows = session.scalars(
        select(Weather).where(Weather.date == on_date).order_by(Weather.zone_id)
    ).all()

    # Fallback: if no rows for on_date, use each zone's latest reading.
    if not rows:
        zone_ids = list(session.scalars(select(Weather.zone_id).distinct()).all())
        latest_rows = []
        for zone_id in zone_ids:
            last = session.scalar(
                select(Weather)
                .where(Weather.zone_id == zone_id, Weather.date <= on_date)
                .order_by(Weather.date.desc())
                .limit(1)
            )
            if last is not None:
                latest_rows.append(last)
        rows = latest_rows

    alerts = []
    for row in rows:
        rainfall_1d = row.rainfall_1d or 0.0
        rainfall_7d = row.rainfall_7d or 0.0
        if rainfall_1d >= RISK_RAINFALL_1D or rainfall_7d >= RISK_RAINFALL_7D:
            alerts.append(
                {
                    "zone_id": row.zone_id,
                    "date": row.date.isoformat(),
                    "rainfall_1d": rainfall_1d,
                    "rainfall_7d": rainfall_7d,
                    "trigger": (
                        "rainfall_1d" if rainfall_1d >= RISK_RAINFALL_1D else "rainfall_7d"
                    ),
                }
            )

    return {
        "date": on_date.isoformat(),
        "thresholds": {"rainfall_1d": RISK_RAINFALL_1D, "rainfall_7d": RISK_RAINFALL_7D},
        "alerts": alerts,
    }
