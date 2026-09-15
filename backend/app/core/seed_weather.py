"""Seed WEATHER data — Phase 8.

Hybrid seeding:
1. HISTORICAL BASELINE (12 months) — tries REAL IMD rainfall first
   (`--real` or automatic attempt); falls back to the synthetic monsoon
   generator when the download fails or no DB zones exist.
2. DEMO SCENARIO TRIGGER — synthetic, flagged `scenario='demo'`, on the
   designated spike date for the at-risk zone (A1) vs favorable zone (B3).

Idempotent upsert on (zone_id, date) — migration 0003.

Demo re-trigger/reset:
    python -m app.core.seed_weather --demo-only          # re-apply trigger
    python -m app.core.seed_weather --demo-reset DATE    # clear + re-apply
    python -m app.core.seed_weather --dry-run            # preview, no writes
"""

import argparse
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models import Weather, Zone
from app.services.synthetic.weather_generator import (
    generate_demo_scenario,
    generate_historical_baseline,
)

IMD_FILE_DIR = "ml/data/raw/imd"
SHAPE_DIR = "ml/data/raw/imd"


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


def _build_upsert(records: list[dict]):
    stmt = insert(Weather).values(records)
    return stmt.on_conflict_do_update(
        index_elements=[Weather.zone_id, Weather.date],
        set_={
            "rainfall_1d": stmt.excluded.rainfall_1d,
            "rainfall_7d": stmt.excluded.rainfall_7d,
            "rainfall_30d": stmt.excluded.rainfall_30d,
            "scenario": stmt.excluded.scenario,
            "updated_at": Weather.updated_at,
        },
    )


def seed_baseline(session, zones, dates) -> int:
    """Try real IMD; fall back to synthetic baseline."""
    records = None
    try:
        from app.services.ingestion.weather_real import fetch_imd_rainfall, build_zone_series

        print("  attempting real IMD rainfall fetch...")
        # Use the most recent full year in the range
        year = max(d.year for d in dates)
        aoi_daily = fetch_imd_rainfall(
            year=year,
            file_dir=IMD_FILE_DIR,
            aoi_bounds=(79.68, 21.62, 79.78, 21.70),
            shp_dir=SHAPE_DIR,
        )
        records = build_zone_series(aoi_daily, zones)
        for r in records:
            r["scenario"] = "historical"
        print(f"  real IMD data: {len(aoi_daily)} days fetched")
    except Exception as exc:
        print(f"  real fetch failed ({exc.__class__.__name__}) - synthetic fallback")

    if records is None:
        records = generate_historical_baseline(zones, dates)

    if not records:
        return 0
    session.execute(_build_upsert(records))
    session.commit()
    return len(records)


def seed_demo(session, zones, spike_date: date | None = None) -> int:
    """Upsert the demo scenario trigger rows."""
    # Demo uses a 7-day window ending on the spike date for rolling sums.
    trigger = spike_date or date.today()
    dates = [trigger - timedelta(days=i) for i in range(6, -1, -1)]
    records = generate_demo_scenario(zones, dates, spike_date=trigger)
    session.execute(_build_upsert(records))
    session.commit()
    return len(records)


def reset_demo(session) -> int:
    """Remove all demo-flagged weather rows (reversible trigger)."""
    result = session.execute(delete(Weather).where(Weather.scenario == "demo"))
    session.commit()
    return result.rowcount


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed WEATHER data.")
    parser.add_argument("--months", type=int, default=12, help="baseline months (default 12)")
    parser.add_argument("--demo-only", action="store_true", help="only (re-)apply demo trigger")
    parser.add_argument("--demo-reset", type=str, metavar="DATE", help="clear demo rows then apply trigger")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        fake_zones = [
            type("FakeZone", (), {"zone_id": f"{r}{c}"})()
            for r in "ABCD"
            for c in "12345"
        ]
        dates = _monthly_dates(args.months, date.today())
        baseline = generate_historical_baseline(fake_zones, dates)
        demo = generate_demo_scenario(
            fake_zones, [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
        )
        print(f"Dry run: {len(baseline)} baseline rows + {len(demo)} demo rows "
              f"({len(fake_zones)} zones x {args.months} months + trigger window).")
        at_risk = [r for r in demo if r["zone_id"] == "A1"]
        print(f"  A1 trigger: 1d={at_risk[-1]['rainfall_1d']}mm, "
              f"7d={at_risk[-1]['rainfall_7d']}mm on {at_risk[-1]['date']}")
        b3 = [r for r in demo if r["zone_id"] == "B3"]
        print(f"  B3 favorable: 1d={b3[-1]['rainfall_1d']}mm, "
              f"7d={b3[-1]['rainfall_7d']}mm")
        return 0

    with SessionLocal() as session:
        zones = list(session.scalars(select(Zone).order_by(Zone.zone_id)).all())

        if not zones:
            print("No zones found — run seed_grid.py first (Phase 4).")
            return 1

        if args.demo_reset:
            removed = reset_demo(session)
            print(f"Removed {removed} demo rows (reset).")

        if args.demo_only:
            count = seed_demo(session, zones, spike_date=date.today())
            print(f"Seeded {count} demo scenario rows.")
            return 0

        dates = _monthly_dates(args.months, date.today())
        baseline_count = seed_baseline(session, zones, dates)
        demo_count = seed_demo(session, zones, spike_date=date.today())
        print(f"Seeded {baseline_count} baseline + {demo_count} demo weather rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
