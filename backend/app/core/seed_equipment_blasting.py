"""Seed EQUIPMENT fleet + status history + BLASTING — Phase 9.

Idempotent upserts: equipment on equipment_id, history on (equipment_id, date),
blasting on blast_id. Both datasets are SYNTHETIC per PRD §38.

Usage:
    python -m app.core.seed_equipment_blasting
    python -m app.core.seed_equipment_blasting --dry-run
"""

import argparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models import Blasting, Equipment, EquipmentStatusHistory, Weather, Zone
from app.services.synthetic.blasting_generator import generate_blasting_records
from app.services.synthetic.equipment_generator import (
    generate_equipment_fleet,
    generate_status_history,
)


def _weather_daily_map(session) -> dict[str, dict]:
    """zone_id -> {date: rainfall_1d} from Phase 8 weather rows."""
    rows = session.execute(
        select(Weather.zone_id, Weather.date, Weather.rainfall_1d)
    ).all()
    out: dict[str, dict] = {}
    for zone_id, d, rain in rows:
        if rain is not None:
            out.setdefault(zone_id, {})[d] = float(rain)
    return out


def seed(session) -> tuple[int, int, int]:
    """Returns (equipment_count, history_count, blasting_count)."""
    fleet = generate_equipment_fleet()
    history = generate_status_history(fleet)

    eq_stmt = insert(Equipment).values(fleet)
    eq_stmt = eq_stmt.on_conflict_do_update(
        index_elements=[Equipment.equipment_id],
        set_={
            "mine_id": eq_stmt.excluded.mine_id,
            "equipment_type": eq_stmt.excluded.equipment_type,
            "current_zone_id": eq_stmt.excluded.current_zone_id,
            "availability": eq_stmt.excluded.availability,
            "operating_hours": eq_stmt.excluded.operating_hours,
            "downtime_hours": eq_stmt.excluded.downtime_hours,
            "maintenance_hours": eq_stmt.excluded.maintenance_hours,
            "capacity": eq_stmt.excluded.capacity,
            "updated_at": Equipment.updated_at,
        },
    )

    hist_stmt = insert(EquipmentStatusHistory).values(history)
    hist_stmt = hist_stmt.on_conflict_do_update(
        index_elements=[EquipmentStatusHistory.equipment_id, EquipmentStatusHistory.date],
        set_={
            "availability": hist_stmt.excluded.availability,
            "operating_hours": hist_stmt.excluded.operating_hours,
            "downtime_hours": hist_stmt.excluded.downtime_hours,
            "maintenance_hours": hist_stmt.excluded.maintenance_hours,
            "updated_at": EquipmentStatusHistory.updated_at,
        },
    )

    zones = list(session.scalars(select(Zone).order_by(Zone.zone_id)).all())
    blasting = generate_blasting_records(zones, weather_daily=_weather_daily_map(session))
    bl_stmt = insert(Blasting).values(blasting)
    bl_stmt = bl_stmt.on_conflict_do_update(
        index_elements=[Blasting.blast_id],
        set_={
            "zone_id": bl_stmt.excluded.zone_id,
            "planned_time": bl_stmt.excluded.planned_time,
            "actual_time": bl_stmt.excluded.actual_time,
            "delay_hours": bl_stmt.excluded.delay_hours,
            "updated_at": Blasting.updated_at,
        },
    )

    session.execute(eq_stmt)
    session.execute(hist_stmt)
    session.execute(bl_stmt)
    session.commit()
    return len(fleet), len(history), len(blasting)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed EQUIPMENT + BLASTING data.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        fleet = generate_equipment_fleet()
        history = generate_status_history(fleet)
        from app.services.synthetic.geological_generator import generate_grid_cells_for_dry_run

        zones = generate_grid_cells_for_dry_run()
        blasting = generate_blasting_records(zones, weather_daily={})
        print(f"Dry run: {len(fleet)} equipment + {len(history)} history rows + "
              f"{len(blasting)} blast records.")
        ex04 = next(u for u in fleet if u["equipment_id"] == "EX-04")
        print(f"  EX-04: zone={ex04['current_zone_id']}, availability={ex04['availability']}, "
              f"downtime={ex04['downtime_hours']}h")
        delays = [b["delay_hours"] for b in blasting]
        print(f"  blast delays: max={max(delays):.1f}h, mean={sum(delays)/len(delays):.1f}h")
        return 0

    with SessionLocal() as session:
        eq_n, hist_n, bl_n = seed(session)
    print(f"Seeded {eq_n} equipment + {hist_n} history rows + {bl_n} blast records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
