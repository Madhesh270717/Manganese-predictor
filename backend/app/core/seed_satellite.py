"""Seed SATELLITE data — Phase 7.

Hybrid approach: attempts REAL Sentinel-2 NDVI via Planetary Computer for
recent dates; fills everything else (LST, soil moisture, spectral features,
and any missing NDVI) with the documented synthetic generator.

Idempotent upsert on (zone_id, date) via a unique index — see migration
0002 in database/migrations/versions/.

Usage:
    python -m app.core.seed_satellite --dates 2025-09-01 2025-10-01 ...
    python -m app.core.seed_satellite --dry-run --months 3
"""

import argparse
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models import Satellite, Zone
from app.services.synthetic.satellite_generator import generate_satellite_records


def _monthly_dates(n_months: int, end: date) -> list[date]:
    dates: list[date] = []
    for i in range(n_months - 1, -1, -1):
        year = end.year
        month = end.month - i
        while month <= 0:
            month += 12
            year -= 1
        dates.append(date(year, month, 1))
    return dates


def seed(session, dates: list[date], real_ndvi: dict | None = None) -> int:
    """Upsert satellite rows for all zones × dates. Returns row count."""
    zones = list(session.scalars(select(Zone).order_by(Zone.zone_id)).all())
    if not zones:
        raise RuntimeError("No zones found — run seed_grid.py first (Phase 4).")

    records = generate_satellite_records(zones, dates, real_ndvi=real_ndvi)

    stmt = insert(Satellite).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Satellite.zone_id, Satellite.date],
        set_={
            "latitude": stmt.excluded.latitude,
            "longitude": stmt.excluded.longitude,
            "location": stmt.excluded.location,
            "ndvi": stmt.excluded.ndvi,
            "lst": stmt.excluded.lst,
            "soil_moisture": stmt.excluded.soil_moisture,
            "spectral_features": stmt.excluded.spectral_features,
            "updated_at": Satellite.updated_at,
        },
    )
    session.execute(stmt)
    session.commit()
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed SATELLITE data.")
    parser.add_argument("--dates", nargs="+", help="ISO dates to generate (default: last 3 months)")
    parser.add_argument("--months", type=int, default=3, help="generate last N months from today")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-real", action="store_true", help="skip the real NDVI fetch attempt")
    args = parser.parse_args()

    if args.dates:
        dates = sorted({date.fromisoformat(d) for d in args.dates})
    else:
        dates = _monthly_dates(args.months, date.today())

    print(f"Generating satellite records for dates: {[d.isoformat() for d in dates]}")

    if args.dry_run:
        from app.services.synthetic.geological_generator import generate_grid_cells_for_dry_run

        zones = generate_grid_cells_for_dry_run()
        records = generate_satellite_records(zones, dates)
        print(f"Dry run: {len(records)} satellite rows would be upserted "
              f"({len(zones)} zones x {len(dates)} dates).")
        sample = records[0]
        print(f"  sample {sample['zone_id']} {sample['date']}: "
              f"ndvi={sample['ndvi']}, lst={sample['lst']}, "
              f"sm={sample['soil_moisture']}, spectral={sample['spectral_features']}")
        return 0

    real_ndvi: dict[str, dict[str, float]] = {}
    with SessionLocal() as session:
        zones_for_fetch = list(session.scalars(select(Zone).order_by(Zone.zone_id)).all())
        if not args.no_real and zones_for_fetch:
            from app.services.ingestion.satellite_real import fetch_ndvi_for_date

            for d in dates:
                try:
                    result = fetch_ndvi_for_date(d, zones_for_fetch)
                    if result is None:
                        print(f"  [{d.isoformat()}] no scene found - synthetic fallback")
                        continue
                    real_ndvi[d.isoformat()] = result
                    print(f"  [{d.isoformat()}] real NDVI fetched for {len(result)} zones")
                except Exception as exc:
                    print(f"  [{d.isoformat()}] real fetch failed ({exc.__class__.__name__}) - synthetic fallback")

        count = seed(session, dates, real_ndvi=real_ndvi or None)
    print(f"Seeded {count} satellite rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
