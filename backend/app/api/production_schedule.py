"""Production + Schedule API — Phase 10 endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import DataSourceMetadata, MiningSchedule, Production
from app.services.synthetic.production_generator import (
    ACTIVE_ZONES,
    CURRENT_PERIOD_DAYS,
    planned_for_day,
)

router = APIRouter(tags=["production-schedule"])


def _confidence_payload(session: Session, dataset_name: str) -> dict:
    try:
        row = session.scalar(
            select(DataSourceMetadata).where(DataSourceMetadata.dataset_name == dataset_name)
        )
    except Exception:
        row = None
    if row is None:
        from app.core.seed_data_sources import DATA_SOURCE_REGISTRY

        entry = next((r for r in DATA_SOURCE_REGISTRY if r["dataset_name"] == dataset_name), None)
        if entry is None:
            return {"dataset": dataset_name, "confidence": "UNKNOWN"}
        return {
            "dataset": dataset_name,
            "source_type": entry["source_type"],
            "confidence_level": entry["confidence_level"],
            "source_name": entry["source_name"],
        }
    return {
        "dataset": row.dataset_name,
        "source_type": row.source_type.value,
        "confidence_level": row.confidence_level.value,
        "source_name": row.source_name,
    }


@router.get("/production/history")
def production_history(
    db: Session = Depends(get_db),
    zone_id: str | None = Query(None),
    mine_id: str | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
) -> dict:
    """Historical production, filterable by zone/mine/date range.

    DB-first with synthetic fallback (DB-less demo machines).
    """
    rows = None
    try:
        stmt = select(Production)
        if zone_id is not None:
            stmt = stmt.where(Production.zone_id == zone_id)
        if mine_id is not None:
            stmt = stmt.where(Production.mine_id == mine_id)
        if start is not None:
            stmt = stmt.where(Production.date >= start)
        if end is not None:
            stmt = stmt.where(Production.date <= end)
        rows = list(db.scalars(stmt.order_by(Production.date, Production.zone_id)).all())
    except Exception:
        rows = None

    if not rows:
        from datetime import timedelta

        from app.services.synthetic.geochemical_generator import generate_geochemical_records
        from app.services.synthetic.geological_generator import (
            generate_geological_records,
            generate_grid_cells_for_dry_run,
        )
        from app.services.synthetic.production_generator import generate_production_records

        fake = generate_grid_cells_for_dry_run()
        geo = generate_geological_records(fake)
        chem = generate_geochemical_records(geo)
        mn_map = {g["zone_id"]: c["mn_concentration"] for g, c in zip(geo, chem)}
        today = date.today()
        dates = [today - timedelta(days=i) for i in range(364, -1, -1)]
        records = generate_production_records(dates, mn_map)

        class _ProdRow:
            pass

        rows = []
        for r in records:
            if zone_id is not None and r["zone_id"] != zone_id:
                continue
            if mine_id is not None and r["mine_id"] != mine_id:
                continue
            if start is not None and r["date"] < start:
                continue
            if end is not None and r["date"] > end:
                continue
            row = _ProdRow()
            for key, value in r.items():
                setattr(row, key, value)
            rows.append(row)
        rows.sort(key=lambda r: (r.date, r.zone_id))
    return {
        "count": len(rows),
        "records": [
            {
                "date": r.date.isoformat(),
                "mine_id": r.mine_id,
                "zone_id": r.zone_id,
                "planned_production": r.planned_production,
                "actual_production": r.actual_production,
                "ore_grade": r.ore_grade,
            }
            for r in rows
        ],
        "confidence": _confidence_payload(db, "Production"),
    }


@router.get("/production/current-target")
def production_current_target(db: Session = Depends(get_db)) -> dict:
    """Current 30-day planned target (the PRD 82,000 t demo figure).

    Computed from the production generator's planned schedule, so the API
    always agrees with the seeded data.
    """
    today = date.today()
    from datetime import timedelta

    current_period_start = today - timedelta(days=CURRENT_PERIOD_DAYS - 1)
    by_zone: dict[str, float] = {}
    for zone_id in ACTIVE_ZONES:
        total = 0.0
        for i in range(CURRENT_PERIOD_DAYS):
            d = current_period_start + timedelta(days=i)
            total += planned_for_day(zone_id, d, current_period_start)
        by_zone[zone_id] = round(total, 1)

    return {
        "period_days": CURRENT_PERIOD_DAYS,
        "start": current_period_start.isoformat(),
        "end": today.isoformat(),
        "planned_total": round(sum(by_zone.values()), 1),
        "by_zone": by_zone,
        "confidence": _confidence_payload(db, "Production"),
    }


@router.get("/schedule/current")
def schedule_current(db: Session = Depends(get_db)) -> dict:
    """Current active/proposed mining schedule (equipment -> zone -> time).

    DB-first with synthetic fallback (DB-less demo machines) — same pattern
    as equipment/production endpoints.
    """
    rows = None
    try:
        rows = list(
            db.scalars(
                select(MiningSchedule).order_by(
                    MiningSchedule.date, MiningSchedule.shift, MiningSchedule.equipment_id
                )
            ).all()
        )
    except Exception:
        rows = None

    if not rows:
        from app.services.synthetic.schedule_generator import generate_current_schedule

        class _Row:
            pass

        rows = []
        for r in generate_current_schedule(days=7):
            row = _Row()
            for key, value in r.items():
                setattr(row, key, value)
            rows.append(row)

    return {
        "count": len(rows),
        "entries": [
            {
                "date": r.date.isoformat(),
                "shift": r.shift,
                "equipment_id": r.equipment_id,
                "zone_id": r.zone_id,
                "operation": r.operation,
                "planned_start": r.planned_start.isoformat() if r.planned_start else None,
                "planned_end": r.planned_end.isoformat() if r.planned_end else None,
                "expected_output": r.expected_output,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
            }
            for r in rows
        ],
        "confidence": _confidence_payload(db, "MiningSchedule"),
    }


@router.get("/schedule/current/by-equipment/{equipment_id}")
def schedule_by_equipment(equipment_id: str, db: Session = Depends(get_db)) -> dict:
    """Schedule entries for one equipment unit."""
    rows = list(
        db.scalars(
            select(MiningSchedule)
            .where(MiningSchedule.equipment_id == equipment_id)
            .order_by(MiningSchedule.date, MiningSchedule.shift)
        ).all()
    )
    if not rows:
        raise HTTPException(
            status_code=404, detail=f"No schedule entries for equipment: {equipment_id}"
        )
    return {
        "equipment_id": equipment_id,
        "count": len(rows),
        "entries": [
            {
                "date": r.date.isoformat(),
                "shift": r.shift,
                "zone_id": r.zone_id,
                "operation": r.operation,
                "planned_start": r.planned_start.isoformat() if r.planned_start else None,
                "planned_end": r.planned_end.isoformat() if r.planned_end else None,
                "expected_output": r.expected_output,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
            }
            for r in rows
        ],
        "confidence": _confidence_payload(db, "MiningSchedule"),
    }
