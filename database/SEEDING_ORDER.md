# Seeding Order — Spotter AI (Phases 4–10)

Run these seed scripts **in order** against the Supabase database. Order
matters because of foreign keys and cross-phase correlations (each phase's
synthetic data references earlier phases' ground truth).

Prerequisites:

1. Supabase project created with PostGIS enabled (Database > Extensions)
2. `DATABASE_URL` set in `backend/.env` (copy from `.env.example`)
3. Migrations applied against Supabase: `cd database && alembic upgrade head`

| # | Phase | Command | What it seeds | Depends on |
| --- | --- | --- | --- | --- |
| 1 | 4 | `python -m app.core.seed_grid` | 20 zone grid (A1–D5) + AOI | — |
| 2 | 3 | `python -m app.core.seed_data_sources` | DATA_SOURCE_METADATA registry (9 rows) | — |
| 3 | 5 | `python -m app.core.seed_geological_geochemical` | GEOLOGICAL + GEOCHEMICAL (ground-truth cluster) | zones |
| 4 | 6 | `python -m app.core.seed_drilling` | EXPLORATION drill holes (sparse) | zones, geochemical |
| 5 | 7 | `python -m app.core.seed_satellite` | SATELLITE time series (hybrid real/synthetic) | zones |
| 6 | 8 | `python -m app.core.seed_weather` | WEATHER baseline + demo trigger | zones |
| 7 | 9 | `python -m app.core.seed_equipment_blasting` | EQUIPMENT fleet + history + BLASTING | zones, weather (delay correlation) |
| 8 | 10 | `python -m app.core.seed_production_schedule` | PRODUCTION history + current MINING_SCHEDULE | zones, weather, equipment, blasting, geochemical |
| 9 | 14 | `python -m app.core.seed_terrain` | ZONE_TERRAIN_ACCESS (slope/access/haul/road) | zones |

## One-shot from backend/

```bash
python -m app.core.seed_grid
python -m app.core.seed_data_sources
python -m app.core.seed_geological_geochemical
python -m app.core.seed_drilling
python -m app.core.seed_satellite
python -m app.core.seed_weather
python -m app.core.seed_equipment_blasting
python -m app.core.seed_production_schedule
python -m app.core.seed_terrain
```

All scripts are idempotent (upsert), so re-running any step is safe.
Use `--dry-run` on any script to preview without touching the DB.

## Demo re-trigger (repeatable)

```bash
python -m app.core.seed_weather --demo-only      # re-apply rainfall spike on A1
python -m app.core.seed_weather --demo-reset 2026-08-28  # clear demo rows, then re-apply
```
