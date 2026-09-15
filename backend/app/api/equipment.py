"""Equipment API — fleet list, unit detail, history, by-zone lookup."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import (
    Blasting,
    DataSourceMetadata,
    Equipment,
    EquipmentStatusHistory,
    Zone,
)

router = APIRouter(tags=["equipment"])


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


def _equipment_payload(unit: Equipment) -> dict:
    return {
        "equipment_id": unit.equipment_id,
        "mine_id": unit.mine_id,
        "equipment_type": unit.equipment_type,
        "current_zone_id": unit.current_zone_id,
        "availability": unit.availability,
        "operating_hours": unit.operating_hours,
        "downtime_hours": unit.downtime_hours,
        "maintenance_hours": unit.maintenance_hours,
        "capacity": unit.capacity,
    }


@router.get("/equipment")
def list_equipment(db: Session = Depends(get_db)) -> dict:
    """All equipment with current status/location.

    DB-first with synthetic fallback — the same pattern used by the
    mineability/prediction services, so the frontend works on DB-less
    demo machines.
    """
    units = None
    try:
        units = list(db.scalars(select(Equipment).order_by(Equipment.equipment_id)).all())
    except Exception:
        units = None

    if not units:
        from app.services.synthetic.equipment_generator import generate_equipment_fleet

        class _FleetUnit:
            pass

        fleet = generate_equipment_fleet()
        units = []
        for u in fleet:
            unit = _FleetUnit()
            for key, value in u.items():
                setattr(unit, key, value)
            units.append(unit)
        units.sort(key=lambda u: u.equipment_id)

    return {
        "count": len(units),
        "equipment": [_equipment_payload(u) for u in units],
        "confidence": _confidence_payload(db, "Equipment"),
    }


@router.get("/equipment/by-zone/{zone_id}")
def equipment_by_zone(zone_id: str, db: Session = Depends(get_db)) -> dict:
    """Equipment currently assigned to a zone (Optimization Phase 18+ lookup).

    Declared BEFORE /equipment/{equipment_id} so "by-zone" is not captured
    by the equipment_id path parameter.
    """
    from app.api.zones import _resolve_zone
    from app.services.synthetic.equipment_generator import generate_equipment_fleet

    if _resolve_zone(db, zone_id) is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    try:
        units = list(
            db.scalars(
                select(Equipment)
                .where(Equipment.current_zone_id == zone_id)
                .order_by(Equipment.equipment_id)
            ).all()
        )
    except Exception:
        # Synthetic fallback (DB-less demo machines).
        fleet = [u for u in generate_equipment_fleet() if u["current_zone_id"] == zone_id]

        class _Unit:
            pass

        units = []
        for u in fleet:
            unit = _Unit()
            for key, value in u.items():
                setattr(unit, key, value)
            units.append(unit)

    return {
        "zone_id": zone_id,
        "count": len(units),
        "equipment": [_equipment_payload(u) for u in units],
        "confidence": _confidence_payload(db, "Equipment"),
    }


@router.get("/equipment/{equipment_id}")
def get_equipment(equipment_id: str, db: Session = Depends(get_db)) -> dict:
    """Single unit detail (DB-first with synthetic fallback)."""
    try:
        unit = db.scalar(select(Equipment).where(Equipment.equipment_id == equipment_id))
    except Exception:
        unit = None
    if unit is None:
        from app.services.synthetic.equipment_generator import generate_equipment_fleet

        fleet = generate_equipment_fleet()
        unit = next((u for u in fleet if u["equipment_id"] == equipment_id), None)
        if unit is None:
            raise HTTPException(status_code=404, detail=f"Equipment not found: {equipment_id}")

        class _Unit:
            pass

        obj = _Unit()
        for key, value in unit.items():
            setattr(obj, key, value)
        unit = obj
    return {
        **_equipment_payload(unit),
        "confidence": _confidence_payload(db, "Equipment"),
    }


@router.get("/equipment/{equipment_id}/history")
def get_equipment_history(equipment_id: str, db: Session = Depends(get_db)) -> dict:
    """Daily availability/downtime time series for one unit.

    DB-first with synthetic fallback (DB-less demo machines).
    """
    from app.services.synthetic.equipment_generator import generate_equipment_fleet

    try:
        unit = db.scalar(select(Equipment).where(Equipment.equipment_id == equipment_id))
    except Exception:
        unit = None
    if unit is None:
        fleet = generate_equipment_fleet()
        if not any(u["equipment_id"] == equipment_id for u in fleet):
            raise HTTPException(status_code=404, detail=f"Equipment not found: {equipment_id}")
        unit = {"equipment_id": equipment_id}  # sentinel for the fallback below

    try:
        rows = list(
            db.scalars(
                select(EquipmentStatusHistory)
                .where(EquipmentStatusHistory.equipment_id == equipment_id)
                .order_by(EquipmentStatusHistory.date)
            ).all()
        )
    except Exception:
        rows = []

    if not rows:
        # Synthetic history: 90 days of availability around the fleet base.
        from datetime import date, timedelta

        import numpy as np

        rng = np.random.default_rng(7)
        fleet = generate_equipment_fleet()
        spec = next((u for u in fleet if u["equipment_id"] == equipment_id), None)
        base = spec["availability"] if spec else 0.85

        class _R:
            pass

        today = date.today()
        rows = []
        for i in range(89, -1, -1):
            row = _R()
            row.date = today - timedelta(days=i)
            avail = float(np.clip(base + rng.normal(0, 0.04), 0.3, 0.98))
            row.availability = round(avail, 3)
            downtime = (1 - avail) * 12.0
            row.operating_hours = round(12.0 - downtime, 1)
            row.downtime_hours = round(downtime, 1)
            row.maintenance_hours = round(downtime * float(rng.uniform(0.4, 0.8)), 1)
            rows.append(row)

    return {
        "equipment_id": equipment_id,
        "count": len(rows),
        "history": [
            {
                "date": r.date.isoformat(),
                "availability": r.availability,
                "operating_hours": r.operating_hours,
                "downtime_hours": r.downtime_hours,
                "maintenance_hours": r.maintenance_hours,
            }
            for r in rows
        ],
        "confidence": _confidence_payload(db, "Equipment"),
    }


@router.get("/zones/{zone_id}/blasting")
def zone_blasting(zone_id: str, db: Session = Depends(get_db)) -> dict:
    """Blast records for a zone."""
    zone = db.scalar(select(Zone).where(Zone.zone_id == zone_id))
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    rows = list(
        db.scalars(
            select(Blasting)
            .where(Blasting.zone_id == zone_id)
            .order_by(Blasting.planned_time)
        ).all()
    )
    return {
        "zone_id": zone_id,
        "count": len(rows),
        "blasts": [
            {
                "blast_id": r.blast_id,
                "zone_id": r.zone_id,
                "planned_time": r.planned_time.isoformat() if r.planned_time else None,
                "actual_time": r.actual_time.isoformat() if r.actual_time else None,
                "delay_hours": r.delay_hours,
            }
            for r in rows
        ],
        "confidence": _confidence_payload(db, "Blasting"),
    }
