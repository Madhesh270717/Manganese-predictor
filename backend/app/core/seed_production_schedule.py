"""Seed PRODUCTION history + current MINING_SCHEDULE — Phase 10.

Final raw-data seed. Requires Phases 4–9 to have run (FK + correlation
dependencies). See database/SEEDING_ORDER.md.

Usage:
    python -m app.core.seed_production_schedule
    python -m app.core.seed_production_schedule --dry-run
"""

import argparse
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models import (
    Blasting,
    EquipmentStatusHistory,
    Geochemical,
    Geological,
    MiningSchedule,
    Production,
    Weather,
    Zone,
)
from app.services.synthetic.production_generator import (
    ACTIVE_ZONES,
    generate_production_records,
)
from app.services.synthetic.schedule_generator import generate_current_schedule


def _zone_mn_map(session) -> dict[str, float]:
    rows = session.execute(
        select(Geological.zone_id, Geochemical.mn_concentration)
        .join(Geochemical, Geochemical.location_id == Geological.location_id)
    ).all()
    return {zone_id: float(mn) for zone_id, mn in rows if mn is not None}


def _weather_daily_map(session) -> dict[str, dict]:
    rows = session.execute(
        select(Weather.zone_id, Weather.date, Weather.rainfall_1d)
    ).all()
    out: dict[str, dict] = {}
    for zone_id, d, rain in rows:
        if rain is not None:
            out.setdefault(zone_id, {})[d] = float(rain)
    return out


def _zone_equipment_availability_map(session) -> dict[str, dict]:
    """Mean daily fleet availability per zone from Phase 9 history.

    Join: EquipmentStatusHistory -> Equipment (for current zone assignment)
    then average availability per zone per date.
    """
    from app.models import Equipment

    unit_zones = dict(
        session.execute(
            select(Equipment.equipment_id, Equipment.current_zone_id)
        ).all()
    )
    rows = session.execute(
        select(
            EquipmentStatusHistory.equipment_id,
            EquipmentStatusHistory.date,
            EquipmentStatusHistory.availability,
        )
    ).all()

    by_zone: dict[str, dict[date, list[float]]] = {}
    for equipment_id, d, avail in rows:
        zone_id = unit_zones.get(equipment_id)
        if zone_id is None or avail is None:
            continue
        by_zone.setdefault(zone_id, {}).setdefault(d, []).append(float(avail))

    return {
        zone_id: {
            d: sum(values) / len(values) for d, values in daily.items()
        }
        for zone_id, daily in by_zone.items()
    }


def _blasting_delay_map(session) -> dict[str, dict]:
    rows = session.execute(
        select(Blasting.zone_id, Blasting.planned_time, Blasting.delay_hours)
    ).all()
    out: dict[str, dict] = {}
    for zone_id, planned, delay in rows:
        if planned is not None and delay is not None:
            out.setdefault(zone_id, {})[planned.date()] = float(delay)
    return out


def seed(session) -> tuple[int, int]:
    """Returns (production_count, schedule_count)."""
    zones = list(session.scalars(select(Zone).order_by(Zone.zone_id)).all())
    if not zones:
        raise RuntimeError("No zones found — run seed_grid.py first (Phase 4).")

    today = date.today()
    dates = [today - timedelta(days=i) for i in range(364, -1, -1)]

    production = generate_production_records(
        dates,
        _zone_mn_map(session),
        weather_daily=_weather_daily_map(session),
        equipment_availability=_zone_equipment_availability_map(session),
        blasting_delays=_blasting_delay_map(session),
    )

    prod_stmt = insert(Production).values(production)
    prod_stmt = prod_stmt.on_conflict_do_update(
        index_elements=[Production.date, Production.zone_id],
        set_={
            "mine_id": prod_stmt.excluded.mine_id,
            "planned_production": prod_stmt.excluded.planned_production,
            "actual_production": prod_stmt.excluded.actual_production,
            "ore_grade": prod_stmt.excluded.ore_grade,
            "updated_at": Production.updated_at,
        },
    )

    schedule = generate_current_schedule(start_date=today, days=7)
    sched_stmt = insert(MiningSchedule).values(schedule)
    sched_stmt = sched_stmt.on_conflict_do_update(
        index_elements=[
            MiningSchedule.date,
            MiningSchedule.shift,
            MiningSchedule.equipment_id,
        ],
        set_={
            "zone_id": sched_stmt.excluded.zone_id,
            "operation": sched_stmt.excluded.operation,
            "planned_start": sched_stmt.excluded.planned_start,
            "planned_end": sched_stmt.excluded.planned_end,
            "expected_output": sched_stmt.excluded.expected_output,
            "status": sched_stmt.excluded.status,
            "updated_at": MiningSchedule.updated_at,
        },
    )

    session.execute(prod_stmt)
    session.execute(sched_stmt)
    session.commit()
    return len(production), len(schedule)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed PRODUCTION + SCHEDULE data.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        from app.services.synthetic.geochemical_generator import generate_geochemical_records
        from app.services.synthetic.geological_generator import (
            generate_geological_records,
            generate_grid_cells_for_dry_run,
        )

        fake_zones = generate_grid_cells_for_dry_run()
        geo = generate_geological_records(fake_zones)
        chem = generate_geochemical_records(geo)
        mn_map = {g["zone_id"]: c["mn_concentration"] for g, c in zip(geo, chem)}

        today = date.today()
        dates = [today - timedelta(days=i) for i in range(364, -1, -1)]
        production = generate_production_records(dates, mn_map)
        from app.services.synthetic.production_generator import current_period_planned_total

        schedule = generate_current_schedule(start_date=today, days=7)
        total = current_period_planned_total(dates)
        print(f"Dry run: {len(production)} production rows + {len(schedule)} schedule rows.")
        print(f"  Current period planned total: {total} t (target 82,000)")
        ex04 = [s for s in schedule if s["equipment_id"] == "EX-04" and s["shift"] == "A"]
        if ex04:
            print(f"  EX-04 first shift: zone={ex04[0]['zone_id']}, "
                  f"operation={ex04[0]['operation']}, status={ex04[0]['status']}")
        return 0

    with SessionLocal() as session:
        prod_n, sched_n = seed(session)
    print(f"Seeded {prod_n} production rows + {sched_n} schedule rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
