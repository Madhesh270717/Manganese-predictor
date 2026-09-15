"""Seed EXPLORATION (drilling) data — Phase 6.

Idempotent upsert keyed on drill_id. Requires Phase 4 (zones) and Phase 5
(geological/geochemical) seeds to have run, since drill-hole grade/thickness
are correlated with the zone-level geochemical signal.

Usage:
    python -m app.core.seed_drilling
    python -m app.core.seed_drilling --dry-run
"""

import argparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models import Exploration, Geochemical, Geological, Zone
from app.services.synthetic.drilling_generator import generate_drilling_records


def zone_mn_map(session) -> dict[str, float]:
    """zone_id -> mn_concentration from Phase 5 geochemical data."""
    rows = session.execute(
        select(Geological.zone_id, Geochemical.mn_concentration)
        .join(Geochemical, Geochemical.location_id == Geological.location_id)
    ).all()
    return {zone_id: float(mn) for zone_id, mn in rows if mn is not None}


def seed(session) -> int:
    """Upsert drill holes for all zones. Returns row count."""
    zones = list(session.scalars(select(Zone).order_by(Zone.zone_id)).all())
    if not zones:
        raise RuntimeError("No zones found — run seed_grid.py first (Phase 4).")

    records = generate_drilling_records(zones, zone_mn_map(session))
    if not records:
        return 0

    stmt = insert(Exploration).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Exploration.drill_id],
        set_={
            "zone_id": stmt.excluded.zone_id,
            "latitude": stmt.excluded.latitude,
            "longitude": stmt.excluded.longitude,
            "location": stmt.excluded.location,
            "depth": stmt.excluded.depth,
            "ore_thickness": stmt.excluded.ore_thickness,
            "mn_grade": stmt.excluded.mn_grade,
            "updated_at": Exploration.updated_at,
        },
    )
    session.execute(stmt)
    session.commit()
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed EXPLORATION drilling data.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        from app.services.synthetic.geochemical_generator import generate_geochemical_records
        from app.services.synthetic.geological_generator import (
            generate_geological_records,
            generate_grid_cells_for_dry_run,
        )

        zones = generate_grid_cells_for_dry_run()
        geo = generate_geological_records(zones)
        chem = generate_geochemical_records(geo)
        mn_map = {g["zone_id"]: c["mn_concentration"] for g, c in zip(geo, chem)}
        records = generate_drilling_records(zones, mn_map)
        print(f"Dry run: {len(records)} drill holes would be upserted.")
        from collections import Counter

        by_zone = Counter(r["zone_id"] for r in records)
        for zone_id in sorted({z.zone_id for z in zones}):
            print(f"  {zone_id}: {by_zone.get(zone_id, 0)} holes")
        return 0

    with SessionLocal() as session:
        count = seed(session)
    print(f"Seeded {count} drill holes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
