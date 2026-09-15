# Data Confidence — Spotter AI

> Per PRD Section 39: the platform must distinguish **real** from **synthetic**
> data at all times and expose a Data Confidence indicator everywhere data is
> shown.

## Registry (implemented in Phase 3)

The authoritative registry lives in the **`DATA_SOURCE_METADATA`** table
(seeded by `python -m app.core.seed_data_sources`). Current rows:

| # | Dataset | source_type | confidence_level | source_name (PRD §38) |
| --- | --- | --- | --- | --- |
| 1 | Geological | synthetic | SYNTHETIC | synthetic-generated (GSI/BhuKosh inaccessible: login-gated) |
| 2 | Satellite | real | HIGH | ISRO/Bhuvan, Sentinel, Landsat |
| 3 | Weather | real | HIGH | IMD, NASA GPM |
| 4 | Production | synthetic | MEDIUM | synthetic-generated (MOIL zone-level data unavailable) |
| 5 | Equipment | synthetic | SYNTHETIC | synthetic-generated |
| 6 | Blasting | synthetic | SYNTHETIC | synthetic-generated |
| 7 | Geochemical | synthetic | SYNTHETIC | synthetic-generated (GSI/NGDR inaccessible: login-gated) |
| 8 | Exploration/Drilling | synthetic | MEDIUM | synthetic-generated (GSI/NGDR inaccessible: login-gated) |
| 9 | MiningSchedule | synthetic | SYNTHETIC | synthetic-generated (operational/internal data) |

> Geological and Geochemical flipped to synthetic in Phase 5 after the
> real-data attempt (GSI BhuKosh / NGDR) confirmed login-gated access with
> no open API. See docs/synthetic_data_assumptions.md §7.1.

## Table structure

| Column | Type | Notes |
| --- | --- | --- |
| id | integer PK | |
| dataset_name | varchar(64), unique | keyed to dataset categories |
| source_type | enum `source_type` | `real` \| `synthetic` |
| confidence_level | enum `confidence_level` | `HIGH` \| `MEDIUM` \| `LOW` \| `SYNTHETIC` |
| source_name | varchar(128) | e.g. "GSI", "Sentinel", "synthetic-generated" |
| last_updated | timestamptz | last registry refresh |
| created_at / updated_at | timestamptz | row timestamps |

## API

- `GET /api/v1/data-confidence` → full summary
  `{datasets: [...], summary: {"Geological": "HIGH", ...}}`
- `GET /api/v1/data-confidence/{dataset}` → one category

## Confidence levels

| Level | Meaning |
| --- | --- |
| HIGH | Real data from authoritative sources, verified against ground truth |
| MEDIUM | Real data with sparse coverage, gaps, or reconciliation lag |
| LOW | Real but heavily imputed or low-quality data |
| SYNTHETIC | Generated data — must always be visibly labeled |

## Rules (enforced from Phase 3 onward)

1. Every dataset used in a model, dashboard, or report must have a registry row.
2. Synthetic data must never be presented as real — every API response touching
   it carries its confidence label, and the frontend renders a `SYNTHETIC` badge.
3. Model outputs built on synthetic data inherit the `SYNTHETIC` label.
4. All derived/processed datasets must link back to their raw source rows.
5. Synthetic generation conventions: see `docs/synthetic_data_assumptions.md`.
6. Data quality flags (missing/stale) come from `app/core/data_quality.py`.
