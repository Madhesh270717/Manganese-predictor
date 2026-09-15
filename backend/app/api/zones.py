"""Zones API — read-only zone grid endpoints (GeoJSON) + per-zone datasets."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import (
    DataSourceMetadata,
    Exploration,
    Geochemical,
    Geological,
    Satellite,
    Zone,
)
from app.services.grid_generation import (
    zone_to_geojson_feature,
    zones_to_geojson_feature_collection,
)
from app.services.synthetic.drilling_generator import compute_drill_density

router = APIRouter(prefix="/zones", tags=["zones"])


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
        "last_updated": row.last_updated.isoformat(),
    }


def _resolve_zone(db: Session, zone_id: str):
    """Zone ORM row (DB) or a synthetic zone-like object (DB-less machines).

    Returns a zone-like object exposing zone_id/geometry, or None when the
    zone id does not exist in either source.
    """
    try:
        zone = db.scalar(select(Zone).where(Zone.zone_id == zone_id))
        if zone is not None:
            return zone
    except Exception:
        pass
    from app.services.synthetic.geological_generator import generate_grid_cells_for_dry_run

    cell = next((c for c in generate_grid_cells_for_dry_run() if c.zone_id == zone_id), None)
    return cell


@router.get("")
def list_zones(db: Session = Depends(get_db)) -> dict:
    """All zones as a GeoJSON FeatureCollection.

    DB-first with synthetic fallback (frontend must work on DB-less demo
    machines — same pattern as equipment/mineability services).
    """
    try:
        zones = list(db.scalars(select(Zone).order_by(Zone.zone_id)).all())
    except Exception:
        zones = None
    if not zones:
        from app.services.synthetic.geological_generator import generate_grid_cells_for_dry_run

        # generate_grid_cells_for_dry_run already returns rows whose
        # .geometry is a WKBElement — reuse directly.
        fake = generate_grid_cells_for_dry_run()

        class _ZoneRow:
            pass

        zones = []
        for cell in fake:
            zone = _ZoneRow()
            zone.zone_id = cell.zone_id
            zone.mine_id = "MOIL-BALAGHAT"
            zone.geometry = cell.geometry
            zone.row_label = None
            zone.col_label = None
            zone.area_sq_m = None
            zones.append(zone)
    return zones_to_geojson_feature_collection(zones)


@router.get("/{zone_id}")
def get_zone(zone_id: str, db: Session = Depends(get_db)) -> dict:
    """Single zone as a GeoJSON Feature."""
    zone = db.scalar(select(Zone).where(Zone.zone_id == zone_id))
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")
    return zone_to_geojson_feature(zone)


@router.get("/{zone_id}/geological")
def get_zone_geological(zone_id: str, db: Session = Depends(get_db)) -> dict:
    """Combined geological + geochemical data for one zone, confidence-tagged.

    Decision (documented in synthetic_data_assumptions.md): kept as a
    separate endpoint rather than embedded in GET /zones/{zone_id}, so the
    grid listing stays lightweight for the Reserve Map screen.
    """
    from app.services.synthetic.geochemical_generator import generate_geochemical_records
    from app.services.synthetic.geological_generator import (
        generate_geological_records,
        generate_grid_cells_for_dry_run,
    )

    zone = _resolve_zone(db, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    try:
        geological = db.scalar(select(Geological).where(Geological.zone_id == zone_id))
    except Exception:
        geological = None

    if geological is None:
        # Synthetic fallback (DB-less demo machines).
        fake = generate_grid_cells_for_dry_run()
        geo = generate_geological_records(fake)
        chem = generate_geochemical_records(geo)

        row = next((g for g in geo if g["zone_id"] == zone_id), None)
        chem_row = next(
            (c for g, c in zip(geo, chem) if g["zone_id"] == zone_id), None
        )
        if row is None:
            raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

        def _d(**kwargs):
            return kwargs

        geological = _d(
            location_id=row["location_id"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            lithology=row["lithology"],
            geological_unit=row["geological_unit"],
            fault_distance=row["fault_distance"],
            lineament_distance=row["lineament_distance"],
        )
        geochemical = (
            {
                "location_id": chem_row["location_id"],
                "mn_concentration": chem_row["mn_concentration"],
                "fe_concentration": chem_row["fe_concentration"],
                "sio2": chem_row["sio2"],
                "other_elements": chem_row["other_elements"],
            }
            if chem_row
            else None
        )
        return {
            "zone_id": zone_id,
            "mine_id": "MOIL-BALAGHAT",
            "geological": geological,
            "geochemical": geochemical,
            "confidence": {
                "geological": _confidence_payload(db, "Geological"),
                "geochemical": _confidence_payload(db, "Geochemical"),
            },
            "source": "synthetic-fallback",
        }

    geochemical = db.scalar(
        select(Geochemical).where(Geochemical.location_id == geological.location_id)
    )

    return {
        "zone_id": zone_id,
        "mine_id": zone.mine_id,
        "geological": {
            "location_id": geological.location_id,
            "latitude": geological.latitude,
            "longitude": geological.longitude,
            "lithology": geological.lithology,
            "geological_unit": geological.geological_unit,
            "fault_distance": geological.fault_distance,
            "lineament_distance": geological.lineament_distance,
        },
        "geochemical": (
            {
                "location_id": geochemical.location_id,
                "mn_concentration": geochemical.mn_concentration,
                "fe_concentration": geochemical.fe_concentration,
                "sio2": geochemical.sio2,
                "other_elements": geochemical.other_elements,
            }
            if geochemical is not None
            else None
        ),
        "confidence": {
            "geological": _confidence_payload(db, "Geological"),
            "geochemical": _confidence_payload(db, "Geochemical"),
        },
    }


def _drill_hole_payload(hole: Exploration) -> dict:
    return {
        "drill_id": hole.drill_id,
        "zone_id": hole.zone_id,
        "latitude": hole.latitude,
        "longitude": hole.longitude,
        "depth": hole.depth,
        "ore_thickness": hole.ore_thickness,
        "mn_grade": hole.mn_grade,
    }


@router.get("/{zone_id}/drilling")
def get_zone_drilling(zone_id: str, db: Session = Depends(get_db)) -> dict:
    """All drill holes for a zone + computed drill density/confidence label."""
    from app.services.synthetic.drilling_generator import generate_drilling_records
    from app.services.synthetic.geochemical_generator import generate_geochemical_records
    from app.services.synthetic.geological_generator import (
        generate_geological_records,
        generate_grid_cells_for_dry_run,
    )

    zone = _resolve_zone(db, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    try:
        holes = list(
            db.scalars(
                select(Exploration)
                .where(Exploration.zone_id == zone_id)
                .order_by(Exploration.drill_id)
            ).all()
        )
    except Exception:
        holes = None

    if not holes:
        # Synthetic fallback (DB-less demo machines).
        fake = generate_grid_cells_for_dry_run()
        geo = generate_geological_records(fake)
        chem = generate_geochemical_records(geo)
        mn_map = {g["zone_id"]: c["mn_concentration"] for g, c in zip(geo, chem)}
        hole_dicts = [
            h for h in generate_drilling_records(fake, mn_map) if h["zone_id"] == zone_id
        ]
        # FakeZone lacks area_sq_m — derive it from the WGS84 bounds.
        from geoalchemy2.shape import to_shape

        bounds = to_shape(zone.geometry).bounds
        area = abs(bounds[2] - bounds[0]) * abs(bounds[3] - bounds[1]) * 1.23e7

        class _H:
            pass

        rows = []
        for h in hole_dicts:
            row = _H()
            for key, value in h.items():
                setattr(row, key, value)
            rows.append(row)

        return {
            "zone_id": zone_id,
            "density": compute_drill_density(len(rows), area),
            "drill_holes": [_drill_hole_payload(r) for r in rows],
            "confidence": _confidence_payload(db, "Exploration/Drilling"),
            "source": "synthetic-fallback",
        }

    return {
        "zone_id": zone_id,
        "density": compute_drill_density(len(holes), zone.area_sq_m),
        "drill_holes": [_drill_hole_payload(h) for h in holes],
        "confidence": _confidence_payload(db, "Exploration/Drilling"),
    }


@router.get("/{zone_id}/drilling/{drill_id}")
def get_drill_hole(zone_id: str, drill_id: str, db: Session = Depends(get_db)) -> dict:
    """Single drill hole detail for a zone."""
    zone = db.scalar(select(Zone).where(Zone.zone_id == zone_id))
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    hole = db.scalar(
        select(Exploration).where(Exploration.drill_id == drill_id, Exploration.zone_id == zone_id)
    )
    if hole is None:
        raise HTTPException(status_code=404, detail=f"Drill hole not found: {drill_id}")
    return {
        **_drill_hole_payload(hole),
        "confidence": _confidence_payload(db, "Exploration/Drilling"),
    }


def _satellite_payload(row) -> dict:
    return {
        "id": getattr(row, "id", None),
        "zone_id": row.zone_id,
        "date": row.date.isoformat(),
        "ndvi": row.ndvi,
        "lst": row.lst,
        "soil_moisture": row.soil_moisture,
        "spectral_features": row.spectral_features,
    }


@router.get("/{zone_id}/satellite")
def get_zone_satellite(
    zone_id: str,
    db: Session = Depends(get_db),
    start: date | None = Query(None, description="Start date (inclusive)"),
    end: date | None = Query(None, description="End date (inclusive)"),
) -> dict:
    """Satellite time series for a zone, optionally filtered by date range."""
    zone = _resolve_zone(db, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    try:
        stmt = select(Satellite).where(Satellite.zone_id == zone_id)
        if start is not None:
            stmt = stmt.where(Satellite.date >= start)
        if end is not None:
            stmt = stmt.where(Satellite.date <= end)
        rows = list(db.scalars(stmt.order_by(Satellite.date)).all())
    except Exception:
        # Synthetic fallback (DB-less demo machines).
        from datetime import timedelta

        from app.services.synthetic.satellite_generator import generate_satellite_records

        today = date.today()
        dates = [today - timedelta(days=30 * i) for i in range(11, -1, -1)]

        class _R:
            def __init__(self, row):
                for key, value in row.items():
                    setattr(self, key, value)

        rows = [
            _R(r)
            for r in generate_satellite_records([zone], dates)
            if r["zone_id"] == zone_id
        ]

    return {
        "zone_id": zone_id,
        "count": len(rows),
        "series": [_satellite_payload(r) for r in rows],
        "confidence": _confidence_payload(db, "Satellite"),
    }


@router.get("/{zone_id}/satellite/latest")
def get_zone_satellite_latest(zone_id: str, db: Session = Depends(get_db)) -> dict:
    """Most recent satellite reading for a zone."""
    zone = _resolve_zone(db, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")

    try:
        row = db.scalar(
            select(Satellite)
            .where(Satellite.zone_id == zone_id)
            .order_by(Satellite.date.desc())
            .limit(1)
        )
    except Exception:
        row = None
    if row is None:
        from datetime import timedelta

        from app.services.synthetic.satellite_generator import generate_satellite_records

        today = date.today()
        dates = [today - timedelta(days=30 * i) for i in range(11, -1, -1)]

        class _R:
            def __init__(self, row):
                for key, value in row.items():
                    setattr(self, key, value)

        rows = [
            _R(r)
            for r in generate_satellite_records([zone], dates)
            if r["zone_id"] == zone_id
        ]
        if not rows:
            raise HTTPException(status_code=404, detail=f"No satellite data for zone: {zone_id}")
        row = rows[-1]
    return {
        **_satellite_payload(row),
        "confidence": _confidence_payload(db, "Satellite"),
    }
