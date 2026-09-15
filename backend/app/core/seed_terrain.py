"""Seed ZONE_TERRAIN_ACCESS — Phase 14.

Idempotent upsert on zone_id. Requires Phase 4 (zones).

Usage:
    python -m app.core.seed_terrain
    python -m app.core.seed_terrain --dry-run
"""

import argparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models import Zone, ZoneTerrainAccess
from app.services.synthetic.terrain_generator import generate_terrain_records


def seed(session) -> int:
    zones = list(session.scalars(select(Zone).order_by(Zone.zone_id)).all())
    if not zones:
        raise RuntimeError("No zones found — run seed_grid.py first (Phase 4).")

    records = generate_terrain_records(zones)
    stmt = insert(ZoneTerrainAccess).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ZoneTerrainAccess.zone_id],
        set_={
            "slope_degrees": stmt.excluded.slope_degrees,
            "accessibility_rating": stmt.excluded.accessibility_rating,
            "haul_distance_km": stmt.excluded.haul_distance_km,
            "road_condition": stmt.excluded.road_condition,
            "updated_at": ZoneTerrainAccess.updated_at,
        },
    )
    session.execute(stmt)
    session.commit()
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed terrain/access data.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        from app.services.synthetic.geological_generator import generate_grid_cells_for_dry_run

        fake_zones = generate_grid_cells_for_dry_run()
        records = generate_terrain_records(fake_zones)
        print(f"Dry run: {len(records)} terrain rows.")
        for r in records:
            if r["zone_id"] in ("B3", "A1", "D5"):
                print(f"  {r['zone_id']}: slope={r['slope_degrees']}, "
                      f"access={r['accessibility_rating']}, road={r['road_condition']}, "
                      f"haul={r['haul_distance_km']}km")
        return 0

    with SessionLocal() as session:
        count = seed(session)
    print(f"Seeded {count} terrain/access rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
