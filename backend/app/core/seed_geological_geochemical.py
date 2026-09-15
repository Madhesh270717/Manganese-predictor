"""Seed GEOLOGICAL + GEOCHEMICAL for all zones — Phase 5.

Idempotent upsert keyed on location_id, so re-running updates in place
without duplicating rows. Requires the Phase 4 grid seed to have run.

Usage:
    python -m app.core.seed_geological_geochemical
    python -m app.core.seed_geological_geochemical --dry-run
"""

import argparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models import Geochemical, Geological, Zone
from app.services.synthetic.geochemical_generator import generate_geochemical_records
from app.services.synthetic.geological_generator import generate_geological_records


def seed(session) -> tuple[int, int]:
    """Upsert geological + geochemical rows for every zone.

    Returns (geological_count, geochemical_count).
    """
    zones = list(session.scalars(select(Zone).order_by(Zone.zone_id)).all())
    if not zones:
        raise RuntimeError("No zones found — run seed_grid.py first (Phase 4).")

    geo_records = generate_geological_records(zones)
    chem_records = generate_geochemical_records(geo_records)

    geo_stmt = insert(Geological).values(geo_records)
    geo_stmt = geo_stmt.on_conflict_do_update(
        index_elements=[Geological.location_id],
        set_={
            "zone_id": geo_stmt.excluded.zone_id,
            "latitude": geo_stmt.excluded.latitude,
            "longitude": geo_stmt.excluded.longitude,
            "location": geo_stmt.excluded.location,
            "lithology": geo_stmt.excluded.lithology,
            "geological_unit": geo_stmt.excluded.geological_unit,
            "fault_distance": geo_stmt.excluded.fault_distance,
            "lineament_distance": geo_stmt.excluded.lineament_distance,
            "updated_at": Geological.updated_at,
        },
    )
    chem_stmt = insert(Geochemical).values(chem_records)
    chem_stmt = chem_stmt.on_conflict_do_update(
        index_elements=[Geochemical.location_id],
        set_={
            "mn_concentration": chem_stmt.excluded.mn_concentration,
            "fe_concentration": chem_stmt.excluded.fe_concentration,
            "sio2": chem_stmt.excluded.sio2,
            "other_elements": chem_stmt.excluded.other_elements,
            "updated_at": Geochemical.updated_at,
        },
    )

    session.execute(geo_stmt)
    session.execute(chem_stmt)
    session.commit()
    return len(geo_records), len(chem_records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed GEOLOGICAL + GEOCHEMICAL data.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        from app.services.synthetic.geological_generator import (
            generate_grid_cells_for_dry_run,
        )

        # Dry-run without a DB: synthesize zone-like rows from the AOI grid.
        cells = generate_grid_cells_for_dry_run()
        geo_records = generate_geological_records(cells)
        chem_records = generate_geochemical_records(geo_records)
        print(
            f"Dry run: {len(geo_records)} geological, "
            f"{len(chem_records)} geochemical rows would be upserted."
        )
        for r in geo_records:
            print(
                f"  {r['zone_id']} -> {r['lithology']} "
                f"(fault {r['fault_distance']} m, lineament {r['lineament_distance']} m)"
            )
        return 0

    with SessionLocal() as session:
        geo_count, chem_count = seed(session)
    print(f"Seeded {geo_count} geological + {chem_count} geochemical rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
