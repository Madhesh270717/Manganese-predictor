"""Source loaders for the feature engineering pipeline — Phase 11.

Two interchangeable backends:
- load_from_db():     queries the live Postgres (requires seeded phases 4–10)
- load_from_synthetic(): regenerates the same data from the Phase 4–10
  generators with fixed seeds — used for tests, dry-runs, and machines
  without a database. Feature builders see identical schemas either way.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import (
    Blasting,
    Equipment,
    EquipmentStatusHistory,
    Exploration,
    Geochemical,
    Geological,
    MiningSchedule,
    Production,
    Satellite,
    Weather,
    Zone,
)


def load_from_db() -> dict[str, pd.DataFrame]:
    """Load all feature sources from Postgres."""
    with SessionLocal() as session:
        return {
            "zones": pd.read_sql(select(Zone), session.bind)[
                ["zone_id", "mine_id", "area_sq_m"]
            ],
            "geological": pd.read_sql(select(Geological), session.bind),
            "geochemical": pd.read_sql(select(Geochemical), session.bind),
            "exploration": pd.read_sql(select(Exploration), session.bind),
            "satellite": pd.read_sql(select(Satellite), session.bind),
            "production": pd.read_sql(select(Production), session.bind),
            "equipment": pd.read_sql(select(Equipment), session.bind),
            "equipment_history": pd.read_sql(select(EquipmentStatusHistory), session.bind),
            "weather": pd.read_sql(select(Weather), session.bind),
            "blasting": pd.read_sql(select(Blasting), session.bind),
            "schedule": pd.read_sql(select(MiningSchedule), session.bind),
        }


def load_from_synthetic() -> dict[str, pd.DataFrame]:
    """Regenerate sources from the Phase 4–10 generators (fixed seeds)."""
    from app.services.synthetic.blasting_generator import generate_blasting_records
    from app.services.synthetic.equipment_generator import (
        generate_equipment_fleet,
        generate_status_history,
    )
    from app.services.synthetic.geochemical_generator import generate_geochemical_records
    from app.services.synthetic.geological_generator import (
        generate_geological_records,
        generate_grid_cells_for_dry_run,
    )
    from app.services.synthetic.production_generator import generate_production_records
    from app.services.synthetic.satellite_generator import generate_satellite_records
    from app.services.synthetic.schedule_generator import generate_current_schedule
    from app.services.synthetic.weather_generator import (
        generate_demo_scenario,
        generate_historical_baseline,
    )

    fake_zones = generate_grid_cells_for_dry_run()
    zone_ids = [z.zone_id for z in fake_zones]

    geo = generate_geological_records(fake_zones)
    chem = generate_geochemical_records(geo)
    mn_map = {g["zone_id"]: c["mn_concentration"] for g, c in zip(geo, chem)}

    today = date.today()
    year_dates = [today - timedelta(days=i) for i in range(364, -1, -1)]
    weather = generate_historical_baseline(fake_zones, year_dates)
    demo = generate_demo_scenario(
        fake_zones, [today - timedelta(days=i) for i in range(6, -1, -1)]
    )
    weather_all = weather + demo
    # Demo rows override baseline for overlapping (zone, date) pairs.
    weather_all = pd.DataFrame(weather_all)
    weather_all = (
        weather_all.sort_values("scenario", ascending=False)  # 'historical' < 'demo'
        .drop_duplicates(subset=["zone_id", "date"], keep="first")
        .sort_values(["zone_id", "date"])
    )

    fleet = generate_equipment_fleet()
    # Cover the full production window so as-of joins are complete.
    history = generate_status_history(fleet, days=len(year_dates))

    blast = generate_blasting_records(fake_zones, weather_daily={}, n_weeks=12)

    production = generate_production_records(year_dates, mn_map)

    sat_dates = [today - timedelta(days=30 * i) for i in range(5, -1, -1)]
    satellite = generate_satellite_records(fake_zones, sat_dates)

    schedule = generate_current_schedule(start_date=today, days=7)

    return {
        "zones": pd.DataFrame(
            [{"zone_id": z.zone_id, "mine_id": "MOIL-BALAGHAT", "area_sq_m": 4_583_399.0} for z in fake_zones]
        ),
        "geological": pd.DataFrame(geo),
        "geochemical": pd.DataFrame(chem),
        "exploration": _exploration_from_generator(fake_zones, mn_map),
        "satellite": pd.DataFrame(satellite),
        "production": pd.DataFrame(production),
        "equipment": pd.DataFrame(fleet),
        "equipment_history": pd.DataFrame(history),
        "weather": weather_all,
        "blasting": pd.DataFrame(blast),
        "schedule": pd.DataFrame(schedule),
    }


def _exploration_from_generator(fake_zones, mn_map) -> pd.DataFrame:
    from app.services.synthetic.drilling_generator import generate_drilling_records

    return pd.DataFrame(generate_drilling_records(fake_zones, mn_map))
