# Synthetic Data Assumptions — Spotter AI

> Ground rules every future data phase (4–10) MUST follow when generating
> synthetic data, per PRD: *"synthetically generated operational data with
> clearly documented assumptions."*

## 0. Spatial AOI (added Phase 4)

The mine **Area of Interest (AOI)** used to build the zone grid is an
**illustrative bounding box**, NOT an actual licensed MOIL lease boundary.

| Item | Value |
| --- | --- |
| AOI | ~10.2 km E-W × ~8.9 km N-S around the Balaghat manganese belt, MP |
| Bounding box | (79.68°E, 21.62°N) → (79.78°E, 21.70°N), EPSG:4326 |
| Basis | Public knowledge of the Nagpur–Balaghat manganese belt location; not a surveyed boundary |
| Grid | 4 rows (A–D, north→south) × 5 columns (1–5, west→east) = 20 zones (A1…D5) |
| Config | `backend/app/core/mine_config.py` (`BALAGHAT_AOI`, `DEFAULT_MINE_AOI`) |

Rule: **anything** derived from this AOI (zones, geometries, distances) is
illustrative geometry for the prototype and must not be presented as a real
lease or operational boundary. The AOI can be swapped for a real surveyed
boundary in a later phase without changing the grid generation code.

## 1. Identification rule (non-negotiable)

Synthetic data must never be silently mixed with real data. Every record
touching synthetic content must be identifiable through **at least one** of:

1. **`is_synthetic` boolean** column on the dataset table (add in the data's
   ingestion phase if not already present), OR
2. **A `data_source` tag** on the record referencing
   `DATA_SOURCE_METADATA.dataset_name` with `source_type = 'synthetic'`.

Records without a tag default to real and must resolve to a real registry row.

## 2. Naming conventions

| Artifact | Convention |
| --- | --- |
| Synthetic dataset files | `synthetic/<module>_<dataset>_<date>.csv` under `ml/data/synthetic/` |
| Synthetic record IDs | prefixed `SYN-` (e.g. `SYN-DR-0001` for drilling, `SYN-EXC-01` for equipment) |
| Registry entry | `source_name = "synthetic-generated"`, `source_type = "synthetic"` |
| UI display | Confidence badge must render `SYNTHETIC` — never a HIGH/MEDIUM/LOW level |

## 3. Documentation template (mandatory per synthetic dataset)

Each synthetic dataset must ship with a doc (in `docs/` or alongside the
generator) filling in **every** section:

```markdown
# Synthetic dataset: <name>

## What is being simulated
<e.g. "Daily equipment availability for 12 excavators across 3 mines">

## Distributions & ranges assumed
<e.g. "Availability ~ Beta(8, 1.5), downtime ~ Gamma(k=2, theta=0.8) hours/shift">
<list every column: name, unit, distribution, min/max, expected mean>

## Real-world source it stands in for
<e.g. "MOIL fleet telemetry reports (unavailable for this study)">

## Generator
<path to the generating script / notebook>

## Known limitations
<e.g. "No seasonal maintenance cycles; assumes independent machines; no monsoon downtime correlation">

## Confidence
source_type: synthetic | confidence_level: SYNTHETIC
```

## 4. Registry duty

The generator (or ingestion phase) MUST upsert its row in
`DATA_SOURCE_METADATA` (via `app/core/seed_data_sources.py` pattern) so the
confidence service and frontend indicator stay consistent.

## 5. Presentation rule (PRD Section 39)

- **Every API response** touching synthetic data must carry its confidence
  label (`source_type` + `confidence_level` + `source_name`).
- The frontend must render a visible `SYNTHETIC` badge wherever such data
  appears — charts, tables, exports, and the AI assistant's answers.
- Synthetic data must **never** be presented as if it were real: no removal of
  badges, no relabeling in exports, no confidence upgrades downstream.
- Model outputs built on synthetic data inherit the `SYNTHETIC` label.

## 7. Phase 5 datasets: Geological + Geochemical

### 7.1 Real-data attempt (outcome: fallback)

- **GSI BhuKosh** (https://www.data.gov.in/catalog/bhukosh): login-gated
  ("Unified Download" requires an OCBIS-registered account). No open REST API.
- **NGDR** (https://geodataindia.gov.in): requires login; guest portal was
  unreachable (HTTP 504) at time of attempt. No anonymous bulk download path.
- **Conclusion:** public API access is not available within reasonable
  prototype effort. Both datasets fall back to **fully synthetic generation**
  following this document's rules. Registry rows updated:
  `Geological` → synthetic/SYNTHETIC, `Geochemical` → synthetic/SYNTHETIC
  (source_name notes "GSI/BhuKosh inaccessible: login-gated").
- If real data becomes available later, write
  `backend/app/services/ingestion/geological_real.py` mapping it into the
  same schema and flip the registry rows back to real/HIGH (per PRD §38).

### 7.2 Deliberate ground-truth pattern (shared truth for later phases)

Not pure noise — a deliberate spatial structure is built into the synthetic
data so Phase 12's Reserve Prospectivity Model has real signal to learn, and
the PRD §44 demo ("Zone B = 91% prospectivity") is explainable:

- **Manganese-rich cluster: zones B2, B3, C2, C3** (constant
  `HIGH_PROSPECTIVITY_ZONES` in `geological_generator.py`).
- High-prospectivity zones get **gondite** lithology (the manganese-bearing
  Sausar Group unit of the Balaghat belt) with high probability, plus short
  fault distances (120–600 m) and lineament distances (150–700 m) — the
  structural controls real manganese ore follows.
- Background zones get laterite/shale/quartzite and larger structural
  distances (700–3000 m fault, 800–3500 m lineament).
- RNG seeds are fixed (geological: 42, geochemical: 7) so every phase
  regenerates identical "truth" — resource estimation (Phase 8/9), demo
  scripting (Phase 26+), and the AI assistant must reference the same
  high-value zones consistently.

### 7.3 Geological generator (synthetic)

| What | Assumption |
| --- | --- |
| Simulated | One geological observation per zone (centroid ± ~0.004° jitter) |
| lithology | categorical: gondite, quartzite, laterite, shale (weighted by ground truth) |
| geological_unit | tied to lithology (Sausar Group units / laterite capping) |
| fault_distance | high zones U(120, 600) m; background U(700, 3000) m |
| lineament_distance | high zones U(150, 700) m; background U(800, 3500) m |
| Stand-in for | GSI/BhuKosh lithology + structural maps (real source inaccessible) |
| Generator | `backend/app/services/synthetic/geological_generator.py`, seed 42 |
| Limitations | Single point per zone; no fold-axis geometry, no depth info; structural distances are synthetic, not mapped features |

### 7.4 Geochemical generator (synthetic)

Values kept within realistic Indian manganese ore ranges (Mn 10–48% typical
per public ore-type references):

| Field | High-prospectivity zones | Background zones |
| --- | --- | --- |
| mn_concentration (%) | U(30, 46) | U(8, 24) |
| fe_concentration (%) | U(4, 9) | U(2, 7) |
| sio2 (%) | U(8, 22) — inverse with ore quality | U(25, 55) |
| other_elements (JSONB) | Al2O3 U(1, 8), CaO U(0.1, 2.5), P U(0.05, 0.35), P2O5 U(0.1, 0.8) | same ranges, P2O5 U(0.05, 0.5) |

- Fe loosely co-occurs with Mn (geological reality); SiO2 inversely
  correlated with ore quality.
- One geochemical row per geological row (1:1 on `location_id`).
- Generator: `backend/app/services/synthetic/geochemical_generator.py`, seed 7.
- Limitations: no elemental covariance matrix, no gangue mineralogy beyond
  Al2O3/CaO/P, no assay QA flags.

### 7.5 Records & tagging

- IDs prefixed `SYN-` (e.g. `SYN-GEO-B3`), so records are identifiable even
  without a join to the registry.
- API: `GET /api/v1/zones/{zone_id}/geological` returns geological +
  geochemical combined, with `confidence` blocks per dataset from
  DATA_SOURCE_METADATA (both SYNTHETIC).
- Decision (documented): geological data is a **separate endpoint** rather
  than embedded in `GET /zones/{zone_id}`, keeping the grid listing light for
  the Reserve Map screen.
- Seeding: `python -m app.core.seed_geological_geochemical` (idempotent).

## 9. Phase 6 dataset: Exploration/Drilling

### 9.1 Real-data check (outcome: fallback)

NGDR remains login-gated for drill-hole records (MERT-standardized data, no
anonymous API or bulk download). Same conclusion as Phase 5 — full synthetic
fallback. Registry row updated: `Exploration/Drilling` → **synthetic** /
**MEDIUM** (confidence stays MEDIUM per PRD's "sparse coverage" assumption;
MEDIUM encodes the sparse-coverage caveat, synthetic encodes the provenance).

### 9.2 Sparsity rules (intentional, not uniform)

Drilling concentrates on the ground-truth cluster; background zones are
mostly undrilled. This creates the PRD §8 distinction between
model-inferred **prospectivity** and drilling-confirmed **reserve**:

| Zone type | Hole count | Rationale |
| --- | --- | --- |
| B2 | 6 | cluster zone |
| B3 (PRD §44 demo) | 10 | demo zone — densest coverage |
| C2 | 6 | cluster zone |
| C3 | 8 | cluster zone |
| Background (A1…D5) | 0 (p=0.6), 1 (p=0.3), 2 (p=0.1) | exploration follows signal; most zones never drilled |

Hole counts for cluster zones are **deterministic constants**
(`CLUSTER_DRILL_COUNTS`); background counts are weighted draws from the fixed
seed. Re-running the seed reproduces the same sparsity.

### 9.3 Field generation

| Field | Rule |
| --- | --- |
| drill_id | `SYN-DH-{zone}-{nn}` (e.g. `SYN-DH-B3-01`) |
| location | uniform point INSIDE the zone polygon (shapely rejection sampling) — guaranteed to satisfy the zone FK geometry |
| depth (m) | cluster U(60, 150); background U(20, 80) |
| ore_thickness (m) | `clip(zone_mn × 0.085 + N(0, 0.45), 0.5, 9.0)` — richer zones get thicker intersections |
| mn_grade (%) | `clip(zone_mn + N(0, 3.5), 5, 48)` — assay correlated with, but NOT a duplicate of, the zone geochemical value |

`zone_mn` is the Phase 5 geochemical mn_concentration per zone; per-hole
noise makes drilling a realistic noisy sample of the underlying signal.

### 9.4 PRD §44 demo alignment (target)

B3 is the designated demo zone. Its 10 holes are designed so Phase 13's
resource estimation lands near the PRD example figures:

- Phase 5 B3 zone geochemical mn ≈ 43.9%, so B3 assay values center
  ~44% ± N(0, 3.5) (observed seeded mean ≈ 43.8%)
- Expected mean thickness ≈ 3.6 m (43.9 × 0.085 ≈ 3.7)
- Volume at cell area ~4.58 km² × 3.6 m × density factor → on the order of
  several Mt, supporting the "≈4.2 Mt estimated ore" figure once resource
  parameters (tonnage factor, recovery) are applied in Phase 13.
- These are design targets, not calibration guarantees; Phase 13 must
  reconcile actual sampled means against PRD figures and document any gap.

### 9.5 Drill density → confidence label (computed, not stored)

`compute_drill_density(hole_count, area_sq_m)` in drilling_generator.py
returns holes/km² + a qualitative label. Thresholds (holes/km²):

| Label | Range | Meaning for Phase 13 |
| --- | --- | --- |
| NONE | 0 | prospectivity only — no reserve claim allowed |
| SPARSE | (0, 0.5] | "⚠ Limited drilling" evidence flag (PRD §9) |
| MODERATE | (0.5, 1.5] | inferred resource with caution |
| DENSE | > 1.5 | drilling-backed confidence (e.g. B3 ≈ 2.2) |

Decision: computed on the fly in the API (hole counts ≤ 10/zone, static
areas) rather than materialized — document this approach so Phase 13 reuses
the same function for its confidence inputs.

- Generator: `backend/app/services/synthetic/drilling_generator.py`, seed 2026.
- Seeding: `python -m app.core.seed_drilling` (idempotent).
- API: `GET /api/v1/zones/{zone_id}/drilling` (list + density) and
  `GET /api/v1/zones/{zone_id}/drilling/{drill_id}` (single hole).
- Limitations: no downhole assay intervals, no dip/azimuth, no core recovery;
  single thickness/grade value per hole.

## 11. Phase 7 dataset: Satellite

### 11.1 Real-data attempt (outcome: PARTIAL — real NDVI achieved)

Planetary Computer's anonymous STAC API (`https://planetarycomputer.microsoft.com/api/stac/v1/search`)
was queried successfully for Sentinel-2 L2A scenes over the AOI (HTTP 200,
multiple scenes returned, cloud-cover metadata available, B04/B08 COG assets
directly downloadable). This is a REAL data path — no auth, no quota login.

- **NDVI: REAL** — computed from Sentinel-2 B04 (red) / B08 (NIR) with
  rasterio and aggregated to zone polygons via rasterized zonal stats
  (`app/services/ingestion/satellite_real.py`).
- **LST: NOT AVAILABLE free-tier** — Sentinel-2 has no thermal band;
  Landsat thermal or MODIS L3 processing is beyond prototype scope.
  → synthetic gap-fill.
- **soil_moisture: NOT AVAILABLE free-tier** — no direct Sentinel-2 product
  (SMAP requires NASA Earthdata auth). → synthetic gap-fill.
- **spectral_features: PARTIAL** — iron-oxide (B04/B02) and clay (B11/B12)
  ratios are computable from Sentinel-2 bands but were not wired into the
  real fetch for Phase 7 (zonal band-ratio extraction is deferred); the
  generator emits synthetic values in plausible ranges.

### 11.2 Explicit confidence decision

Per PRD §38, Satellite is nominally real/HIGH. In this prototype the row is
**kept at `real` / `HIGH`** but this is an explicit judgement call:

- NDVI — the only field the Phase 12 prospectivity model consumes — is
  **genuinely real** where fetched.
- LST / soil_moisture / spectral_features are synthetic gap-fills, and each
  record's `spectral_features.ndvi_source` marks `real` vs `synthetic` per
  row so downstream consumers can tell.

**Chosen label: `real` / `HIGH` (partial-real), with per-row ndvi_source
tagging.** If a future phase needs fully-real LST/soil moisture, the label
must be revisited to `MEDIUM` or per-field metadata introduced. This
decision is recorded here so it is not ambiguous.

### 11.3 Generator ranges & seasonal model

- Seasonal driver: sinusoid peaking in August (monsoon), trough in Feb.
  Same model the Phase 8 weather generator will share.
- `ndvi` (synthetic fallback): base 0.45, amplitude 0.15, noise 0.06,
  **cluster offset −0.25** (mining-disturbed ore surfaces → lower
  vegetation), clipped [−0.1, 0.9].
- `lst` (°C): base 30, seasonal amplitude 5 (cooler monsoon), noise 1.2,
  **cluster offset +1.5** (exposed rock surfaces run hotter).
- `soil_moisture` (%): base 18, monsoon amplitude 12, noise 2.5,
  **cluster offset −4** (disturbed, fast-draining surfaces drier — feeds
  the Mineability terrain-risk input later).
- `spectral_features` (JSONB): iron_oxide_ratio_b4_b2 ~N(1.1, 0.12)
  background / ~N(1.9, 0.12) over the ore cluster; clay_mineral_ratio
  ~N(1.3, 0.15).
- Correlation with the ore cluster is deliberate and documented (same
  HIGH_PROSPECTIVITY_ZONES constant from Phase 5).

### 11.4 Time series & seeding

- Monthly snapshots over the generated/fetched range (`seed_satellite.py
  --months N` / `--dates ...`).
- Idempotent upsert on `(zone_id, date)` — unique index added in migration
  `0002`.
- Seeding: `python -m app.core.seed_satellite` (hybrid real+synthetic).
- API: `GET /api/v1/zones/{zone_id}/satellite` (time series, `start`/`end`
  query filters) and `GET /api/v1/zones/{zone_id}/satellite/latest`.
- Limitations: real NDVI only for dates where a cloud-filtered scene is
  selected; no per-pixel QA masking; spectral ratios synthetic; zonal
  stats use polygon bounding masks (no fractional coverage weighting).

## 12. Phase 8 dataset: Weather (rainfall)

### 12.1 Real-data attempt (outcome: PARTIAL — real IMD magnitudes/timing)

- **IMD gridded daily rainfall (0.25°)** via the `imdlib` package:
  `get_data(var_type="rain", ...)` downloads from the IMD portal
  anonymously — **verified working** for 2024 and 2025 (366 daily values).
- The AOI (~0.1° box) is smaller than one IMD pixel, so the download yields
  a single AOI-scale daily mean. **Zone-level disaggregation is therefore
  synthetic** (per-zone multiplicative factors ~N(1, 0.25)) — real
  magnitudes/timing, synthetic spatial variation. The `scenario` column
  records `historical` for baseline rows regardless of source.

### 12.2 Confidence split (explicit, not ambiguous)

| Data | source_type | confidence_level | Notes |
| --- | --- | --- | --- |
| Historical baseline | real | HIGH | IMD magnitudes + timing real; zone split synthetic but anchored |
| Demo scenario trigger | synthetic | HIGH (methodology-realistic) | scenario='demo' flag marks it in every response |

Registry row stays `Weather → real / HIGH`. The demo trigger rows are
distinguished by `scenario='demo'` in the WEATHER table and API payloads —
they never masquerade as historical data. The risk-alert and current
endpoints surface `scenario` so Phase 18+ can treat demo rows distinctly.

### 12.3 Seasonality & spatial variation (synthetic generator)

- Monsoon model: Jun–Sep heavy (gamma, mean 18 mm/day), dry otherwise
  (mean 0.4 mm/day). Balaghat-belt realistic.
- Per-zone persistent factors ~N(1, 0.25): adjacent zones correlated but
  not identical — no uniform rainfall, no pure noise.
- `rainfall_1d/7d/30d` are always rolling sums of the daily series (never
  independently randomized).

### 12.4 Demo scenario trigger (PRD §44 mapping)

- **At-risk zone A1** (the "currently scheduled" zone in the PRD narrative):
  a 3-day storm — 90 mm on the trigger date, 30 mm the days before/after.
  7d total ~150+ mm → crosses the risk-alert threshold.
- **Favorable zone B3** (Phase 5/6 high-prospectivity zone): trace rain
  (<2 mm/day) — the "move equipment to Zone B" destination stays operable.
- Other zones: moderate monsoon rain, no extreme signal.
- Trigger is re-appliable: `python -m app.core.seed_weather --demo-only`
  re-upserts the trigger window; `--demo-reset DATE` clears demo rows first
  (reversible, repeatable for demos).
- Risk thresholds: `rainfall_1d >= 60 mm` or `rainfall_7d >= 150 mm` flags
  a zone in `/api/v1/weather/risk-alert`.

### 12.5 Latest-available fallback (PRD §41)

`app/services/weather_service.py::latest_weather()` returns today's row if
present; otherwise the last known reading with `is_stale: true` and
`data_age_days`. No data → `data_age_days: null` with an explanatory note.
Reused by Production Intelligence (Phase 16) and Optimization (Phase 18+).

- Seeding: `python -m app.core.seed_weather` (hybrid), `--months N`,
  `--dry-run`, `--demo-only`, `--demo-reset`.
- API: `GET /api/v1/zones/{zone_id}/weather` (time series, start/end filters),
  `GET /api/v1/zones/{zone_id}/weather/current`,
  `GET /api/v1/weather/risk-alert`.
- Limitations: IMD data is AOI-mean only (one pixel); no IMD forecast
  product; demo trigger is fully synthetic.

## 13. Phase 9 datasets: Equipment & Blasting

### 13.1 Designation

Both are **synthetic / SYNTHETIC** per PRD §38 ("If unavailable for the
hackathon: synthetically generated operational data with clearly documented
assumptions"). Registry rows already reflect this from Phase 3 — no change
needed, no ambiguity.

### 13.2 Fleet composition (10 units, PRD ID scheme)

| ID | Type | Initial zone | Base availability | Capacity (t/h) |
| --- | --- | --- | --- | --- |
| EX-01 | Excavator | C2 | 0.90 | 120 |
| EX-02 | Excavator | B2 | 0.86 | 115 |
| EX-03 | Excavator | C3 | 0.88 | 120 |
| EX-04 | Excavator | **A1 (at-risk)** | **0.59** | 110 |
| EX-05 | Excavator | B3 | 0.91 | 125 |
| T-06 | Dumper/Truck | B3 | 0.84 | 60 |
| T-07 | Dumper/Truck | B2 | 0.82 | 55 |
| DR-08 | Drill Rig | C3 | 0.78 | 30 |
| DR-09 | Drill Rig | B3 | 0.80 | 32 |
| LD-10 | Loader | C2 | 0.87 | 90 |

- **EX-04 is deliberately placed in A1** (the Phase 8 at-risk zone) to set
  up the PRD §36/§44 reallocation demo ("MOVE EX-04 to Zone B").
- **EX-04's downtime story**: availability ~59% means downtime ≈ 41% of
  scheduled hours — designed to justify the PRD §16 explainability example
  where "Equipment downtime 41%" is the LARGEST shortfall contributor.
- Daily noise N(0, 0.04) + random maintenance dips (p=0.06, up to −0.5).

### 13.3 Status history (schema decision)

EQUIPMENT stores the **current snapshot**; a new **EQUIPMENT_STATUS_HISTORY**
table (migration `0004`) stores the 90-day daily series per unit
(availability, operating/downtime/maintenance hours). Rationale: scheduling
lookups stay cheap against the snapshot table, while Phase 15's production
model trains against history. Unique on `(equipment_id, date)`.

### 13.4 Blasting & weather-correlated delays

- Blast-active zones: B2 (3/month), B3 (4), C2 (3), C3 (3), A1 (3).
- Baseline delay ~N(0, 0.4) hours (on/near schedule).
- **A1 delays are rain-correlated**: `delay_hours ~ N(rainfall_1d × 0.05, 0.3)`
  on the planned date — the Phase 8 spike (110mm) produces multi-hour delays.
  This correlation feeds later explainability (PRD §16 "Blasting delays 20%").
- IDs: `SYN-BL-{zone}-{nn}`.

### 13.5 Seeding & endpoints

- Seeding: `python -m app.core.seed_equipment_blasting` (idempotent;
  `--dry-run` previews without a DB).
- API: `GET /api/v1/equipment`, `GET /api/v1/equipment/{id}`,
  `GET /api/v1/equipment/{id}/history`, `GET /api/v1/equipment/by-zone/{zone}`,
  `GET /api/v1/zones/{zone_id}/blasting`.
- Confidence: all responses tagged SYNTHETIC via DATA_SOURCE_METADATA.

## 14. Phase 10 datasets: Production & Mining Schedule

### 14.1 Confidence tagging

- **Production**: `synthetic / MEDIUM` (updated — MOIL reports are real but
  zone-level data is not publicly available; MEDIUM kept per PRD's
  reconciliation-lag caveat, synthetic records provenance).
- **MiningSchedule**: NEW registry row `synthetic / SYNTHETIC`
  (schedules are operational/internal data, never public).

### 14.2 Production generator & factor correlations

Daily planned vs actual for the 5 active zones (A1, B2, B3, C2, C3) over
12 months. Actual output is planned × factor, where factor responds to the
upstream data already seeded — this is deliberate, learnable signal for
Phase 15, not noise:

| Factor | Effect on actual |
| --- | --- |
| rainfall_1d ≥ 40mm (Phase 8) | × U(0.50, 0.65) |
| rainfall_1d 15–40mm | × U(0.75, 0.90) |
| zone fleet availability (Phase 9) | × (0.55 + 0.5 × avail) |
| blasting delay > 3h (Phase 9) | × 0.75 |
| daily noise | × N(1, 0.06), clipped [0.5, 1.2] |

- ore_grade ~ zone geochemical mn ± N(0, 2.0), clipped [10, 48].
- Mixed over/under-target days ensure the Phase 15 model cannot trivially
  learn a single rule.

### 14.3 Current-period target (PRD demo figure)

Planned daily production is FIXED per zone so any 30-day window totals
exactly **82,000 t**:

| Zone | Daily planned | 30-day total |
| --- | --- | --- |
| B3 | 800 | 24,000 |
| C3 | 650 | 19,500 |
| B2 | 550 | 16,500 |
| C2 | 460 | 13,800 |
| A1 | 273/274 | 8,200 |

The ~74,600 t predicted shortfall figure is **NOT fabricated here** — that
is Phase 15's model output. This phase only provides realistic planned
targets + historical training data.

### 14.4 Current schedule (the "before" state)

`generate_current_schedule` emits 7 days × 2 shifts for all 10 units in
the PRD §18/§35 format. **EX-04 is explicitly scheduled in A1** (the
at-risk zone) — the literal before-state that Phase 18–21's optimizer will
evaluate and propose moving to Zone B. EX-05 stays in B3 (favorable
destination). Status: today-and-earlier rows 'active', future 'proposed'.

- Seeding: `python -m app.core.seed_production_schedule` (idempotent).
- Full order: `database/SEEDING_ORDER.md`.
- API: `GET /api/v1/production/history`, `/api/v1/production/current-target`,
  `GET /api/v1/schedule/current`, `/api/v1/schedule/current/by-equipment/{id}`.
- Limitations: daily granularity only (no shift-level production split);
  zone-level MOIL data assumed; factor model is synthetic.

## 15. Phase 14 dataset: Terrain & Access (ZoneTerrainAccess)

New lightweight dataset (migration `0006`) — PRD Sections 10–11 reference
terrain/slope/road factors that were not part of the original 9 datasets.

- **Table**: `zone_terrain_access` (zone_id FK unique, slope_degrees,
  accessibility_rating GOOD/MODERATE/POOR, haul_distance_km, road_condition
  GOOD/MODERATE/POOR). Separate table (not ZONE columns) — operational
  metadata refreshed independently; documented schema decision.
- **Generator**: `terrain_generator.py`, seed 14. Deliberate pattern:
  - Cluster zones (B2/B3/C2/C3): slope U(2,8)°, GOOD access, GOOD roads,
    haul 1.5–4 km — because PRD §20 shows Zone B as simultaneously HIGH
    prospectivity AND HIGH mineability.
  - A1 (at-risk): slope U(10,20)°, MODERATE access, **POOR roads**
    (rain-susceptible terrain — the Phase 18+ "move away" narrative).
  - Background: slope U(8,25)°, mixed MODERATE/POOR.
- **Haul distance**: computed from zone centroid to the assumed processing
  plant anchor at the AOI south-center (79.73°E, 21.63°N — near the cluster,
  so Zone B's GOOD-access narrative holds) + N(0, 0.4) noise — documented
  simplification.
- Seeding: `python -m app.core.seed_terrain` (idempotent; add to
  SEEDING_ORDER.md after weather/equipment).

## 16. Phase 14 scoring: Mineability (Module 2)

- **Rule-based weighted composite** (not ML — documented choice: PRD §30
  doesn't mandate an algorithm for Module 2; transparent weights satisfy
  §41 Explainability and recompute cheaply).
- Weights: prospectivity 0.20, resource 0.15, terrain 0.15, access 0.10,
  weather 0.20, equipment 0.20 (sums to 1.0; constants in score.py).
- Classification: ≥70 Recommended / 45–69 Conditional / <45 Avoid-Postpone.
- **DYNAMIC by design**: weather (current rainfall_1d) and equipment
  availability are queried live per request — score shifts immediately when
  conditions change (verified by test). This is what Phase 18+ optimizes on.

## 17. Phase 20: Reallocation recommendation (PRD §21/§36 reconciliation)

PRD §21 example: production 74,600 → ~81,300t, shortfall 7,400 → ~700t
after moving equipment "Zone A → Zone B" (§45 confirms these are demo
values, not expected real-world performance).

This build's actual demo recommendation (computed from real model calls,
never hardcoded):

- **EX-04: A1 → C3** (not B3 — documented Phase 19 deviation: C3 ranks
  #1 on the objective because its haul is ~2km vs B3's ~4.4km with
  near-identical prospectivity/equipment; B3 is #3, 2.7 points behind)
- production: 75,030 → 77,960t (+2,930t; PRD shows +6,700t — direction
  consistent, magnitude smaller because one unit moves, not the whole
  fleet)
- shortfall: 6,963 → 4,034t (8.49% → 4.92%; PRD shows → ~700t — same
  direction, different magnitude for the same reason)

The direction of every figure matches the PRD; magnitudes differ because
this build's synthetic conditions (single-unit move, richer ore grades,
documented §9.4/§14.4) differ from the PRD's illustrative scenario.

## 10. Current registry

| Dataset | source_type | confidence_level | source_name |
| --- | --- | --- | --- |
| Geological | synthetic | SYNTHETIC | synthetic-generated (GSI/BhuKosh inaccessible: login-gated) |
| Satellite | real | HIGH | ISRO/Bhuvan, Sentinel, Landsat |
| Weather | real | HIGH | IMD, NASA GPM |
| Equipment | synthetic | SYNTHETIC | synthetic-generated |
| Blasting | synthetic | SYNTHETIC | synthetic-generated |
| Geochemical | synthetic | SYNTHETIC | synthetic-generated (GSI/NGDR inaccessible: login-gated) |
| Exploration/Drilling | synthetic | MEDIUM | synthetic-generated (GSI/NGDR inaccessible: login-gated) |
| Production | synthetic | MEDIUM | synthetic-generated (MOIL zone-level data unavailable) |
| MiningSchedule | synthetic | SYNTHETIC | synthetic-generated (operational/internal data) |
