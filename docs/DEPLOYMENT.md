# Spotter AI — Setup & First-Run Guide (Supabase, no Docker)

## Prerequisites

- Python 3.11+ and Node.js 18+ on the local machine — **no Docker, no
  containers anywhere**
- A free Supabase project (https://supabase.com) with **PostGIS enabled**
  (Database > Extensions > enable `postgis`)

## 1. Supabase setup (one-time, manual)

1. Create a free Supabase project.
2. In the dashboard, go to **Database > Extensions** and enable `postgis`.
3. Go to **Project Settings > Database**, copy the **Connection string
   (URI)** — it looks like
   `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`.
4. Save it to `backend/.env` (copy from `.env.example`):

   ```bash
   cd backend
   cp .env.example .env
   # edit .env → set DATABASE_URL=<your Supabase URI>
   ```

   The backend accepts `postgres://` or `postgresql://` and normalizes to
   psycopg2. It will **not start** without `DATABASE_URL`.

## 2. Backend (Python venv)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  /  source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Verify connectivity:

```bash
curl http://localhost:8000/health
# → {"status":"ok","service":"spotter-ai-backend","db_connected":true,
#    "postgis_available":true,"db_error":null}
```

`/health` performs a real `SELECT 1` plus a PostGIS function check against
Supabase — `db_connected: true` means the connection string works.

## 3. Database migrations (Alembic → Supabase)

Migrations live in `database/` and read the same `backend/.env`:

```bash
cd database
alembic upgrade head
```

Alembic's `env.py` resolves `DATABASE_URL` from `backend/app/core/config.py`
(which reads `backend/.env`), so migrations run against the Supabase
instance, never a local database.

## 4. Seed the demo data

From `backend/` (idempotent — safe to re-run):

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
python -m app.core.seed_weather --demo-only
```

## 5. Frontend (npm)

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The frontend calls the backend at `http://localhost:8000` by default
(`VITE_API_BASE_URL` env var to override).

## Model artifacts

The Phase 12/15 trained models live in `ml/pipelines/*/artifacts/` and load
lazily on first prediction. To retrain:

```bash
cd ml/pipelines/reserve_model && python train.py
cd ../production_model && python train.py
```

## Demo reset (repeatable runs)

After a demo run, restore the pre-demo state:

```bash
cd backend
python -m app.core.reset_demo_scenario
```

This clears the accepted recommendation, clears the in-memory pending
registry, and re-applies the A1 rainfall trigger. Use `--no-weather` to skip
the trigger.

## Presentation runbook

See **docs/DEMO_SCRIPT.md** for the 12-step PRD Section 44 demo walkthrough.
