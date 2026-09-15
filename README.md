# Spotter AI

AI-powered **Manganese Reserve Mapping, Production Prediction & Dynamic Mine Scheduling** — the complete MVP built for the Smart India Hackathon (PRD Section 43).

Everything is live: 7 frontend screens wired to a unified FastAPI backend, 4 ML models, an OR-Tools optimization engine, and a retrieval-grounded LLM assistant. All model outputs are explicitly statistical/prototype values on synthetic demo data (PRD Section 45) — not claims of real-world mining performance.

## Modules

| Module | What it does | Tech |
| --- | --- | --- |
| Reserve Intelligence | Prospectivity model + statistical resource estimation (tonnage/grade/contained Mn) | scikit-learn, XGBoost, GeoPandas |
| Mineability Analysis | Live geotechnical feasibility scoring (weather/equipment aware) | scikit-learn |
| Production Intelligence | Production forecasting + shortfall risk + SHAP cause attribution | XGBoost, SHAP |
| Dynamic Scheduling | Constraint-based reallocation, candidate ranking, recommendations | Google OR-Tools |
| AI Assistant | Natural-language Q&A grounded in real model results (tool-use) | Anthropic API (optional key) |

## Screens

| # | Screen | Route | Backed by |
| --- | --- | --- | --- |
| 1 | Overview | `/overview` | prospectivity, prediction, shortfall, equipment |
| 2 | Reserve Map | `/reserve-map` | zone grid + prospectivity + resource estimates + drilling/geology |
| 3 | Production | `/production` | history, target, prediction, shortfall |
| 4 | Risk Analysis | `/risk-analysis` | shortfall risk, SHAP causes, reallocation triggers, weather alerts |
| 5 | Dynamic Schedule | `/schedule` | current schedule, fleet, PRD §22 validation, recalculation |
| 6 | Recommendations | `/recommendations` | Phase 20 move recommendations + accept/reset demo |
| 7 | Spotter AI Assistant | `/assistant` | grounded LLM chat over all modules |
| — | Success Metrics | `/metrics` | PRD §45 evaluation reports + demo impact |

## Quick start (Supabase — no Docker)

```bash
# 1. Create a free Supabase project, enable PostGIS (Database > Extensions),
#    copy the connection URI from Project Settings > Database.
cd backend
cp .env.example .env          # paste your DATABASE_URL into .env
python -m venv .venv
.venv\Scripts\activate        # Windows  /  source .venv/bin/activate
pip install -r requirements.txt

# 2. Migrate + seed (runs against Supabase)
cd ../database
alembic upgrade head
cd ../backend
python -m app.core.seed_grid && python -m app.core.seed_data_sources && \
python -m app.core.seed_geological_geochemical && python -m app.core.seed_drilling && \
python -m app.core.seed_satellite && python -m app.core.seed_weather && \
python -m app.core.seed_equipment_blasting && python -m app.core.seed_production_schedule && \
python -m app.core.seed_terrain && python -m app.core.seed_weather --demo-only

# 3. Backend
uvicorn app.main:app --reload       # http://localhost:8000/health → db_connected: true

# 4. Frontend (separate terminal)
cd ../frontend
npm install
npm run dev                         # http://localhost:5173
```

Full setup details (env vars, seeding, demo reset): **docs/DEPLOYMENT.md**.

## The 12-step demo

The complete hackathon presentation runbook is in **docs/DEMO_SCRIPT.md** —
from "Spotter AI identifies Zone B at ~93% prospectivity" through the
EX-04 A1→C3 reallocation to "Spotter AI explains the decision". The demo is
repeatable: `python -m app.core.reset_demo_scenario` restores the pre-run state.

## Repository structure

```
spotter-ai/
├── backend/       FastAPI API (routers, services, seed scripts, .env with DATABASE_URL)
├── ml/            ML pipelines (models, training, evaluation reports, parquet data)
├── frontend/      React + Vite SPA (8 screens, shared design system)
├── database/      Alembic migrations (run against Supabase) + SEEDING_ORDER.md
├── docs/          DEMO_SCRIPT.md, DEPLOYMENT.md, API_REFERENCE.md, data notes
└── README.md
```

## Key API endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/reserve/prospectivity` | Zone prospectivity scores (P12) |
| `GET /api/v1/reserve/resource-estimate/{zone}` | Resource estimate (P13) |
| `GET /api/v1/mineability` | Live mineability ranking (P14) |
| `GET /api/v1/production/predict/current` | Production forecast (P15) |
| `GET /api/v1/production/shortfall/current` | Shortfall + risk (P16) |
| `GET /api/v1/production/shortfall/current/explain` | SHAP cause attribution (P17) |
| `GET /api/v1/optimization/risks` | Risk triggers (P19) |
| `GET /api/v1/recommendations` | Reallocation recommendations (P20) |
| `POST /api/v1/assistant/chat` | Grounded AI assistant (P29) |
| `GET /api/v1/metrics/summary` | PRD §45 success metrics (P30) |
| `POST /api/v1/demo/accept` · `POST /api/v1/demo/reset` | Demo state control (P30) |

Mutating POST endpoints require `X-API-Key: spotter-demo` (env-configurable).
Full map: **docs/API_REFERENCE.md**.

## Status

All 30 phases complete. All 5 modules and all 11 PRD "Must Have" items
(prospectivity map, resource estimation, production prediction, shortfall
detection, cause analysis, dynamic zone selection, equipment reassignment,
schedule optimization, recommendation dashboard, Spotter AI chatbot) are
implemented, tested (196 backend tests), and demo-ready.
