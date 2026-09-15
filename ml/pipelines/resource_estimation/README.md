# Resource Estimation — Phase 13 (Module 1, PRD Sections 8–9)

## What this is

A **statistical resource estimate** for each zone with sufficient drilling:
estimated ore volume (m³), tonnage (t), average Mn grade (%), contained
manganese (t), and a confidence level. Every output is
`data_type: "statistical_estimate"` — **NOT a certified reserve/resource**
under JORC/UNFC or any formal classification (PRD Section 8).

## Methodology (chosen + justified)

PRD Section 30 allows Regression / Spatial Interpolation / Kriging /
Geological Modelling. This prototype uses a **simplified geometric +
regression substitute**:

1. **Volume (geometric, drill-influence)**: each drill hole influences a
   circular area of radius **100 m** (documented assumption — a standard
   "influence radius" simplification). Effective mineralized area per zone =
   `min(n_holes × π × 100², zone_area)`. Volume = effective area × mean ore
   thickness.
2. **Thickness (regression for weakly-drilled zones)**: for zones with ≥4
   holes (B2/B3/C2/C3) the drill-average thickness is used directly. For
   sparse zones (1–2 holes) thickness is predicted by a linear regression
   `thickness = a + b × mn_concentration` fitted on the strong zones —
   the Phase 11 geochemical signal calibrates where drilling is thin.
3. **Tonnage**: volume × bulk density **3.5 t/m³** (documented value —
   manganese ores with silicate/carbonate gangue typically convert at
   3.0–3.5 t/m³; 3.5 is the conservative upper-mid value).
4. **Grade**: zone-average of drill assay `mn_grade` (Phase 6).
5. **Contained Mn**: tonnage × grade.

Kriging/full geological modelling would be used in a production system;
this prototype substitutes the simplified defensible approach above. The
regression is honest calibration — fitted only on strongly-drilled zones,
never on the zones it predicts.

## Confidence rule (derived from Phase 6 drilling density)

| Drilling density (Phase 6) | Confidence | Rationale |
| --- | --- | --- |
| NONE (0 holes) | NOT_ESTIMATED | `insufficient_data=true` — no numbers, PRD §9 "⚠ Limited drilling" |
| SPARSE | LOW | wide uncertainty range (±50%) |
| MODERATE | MEDIUM | drilling-backed estimate, ±25% range |
| DENSE | MEDIUM | **deliberate**: the PRD's own example rates its densest-drilled zone (B3) as MEDIUM; HIGH is reserved for certified real data. No synthetic prototype data can reach HIGH. |

Grade consistency downgrade: if within-zone assay CV (std/mean) > 30%,
a MEDIUM zone is downgraded to LOW (scattered grades = weaker support).

## Validation against the PRD example (explicit reconciliation)

PRD §8 example for B3: volume 1.2M m³, tonnage 4.2M t, grade 32%,
contained Mn 1.34M t, confidence MEDIUM.

This pipeline's B3 output (documented, not forced):

- volume ≈ **1.12M m³** (10 holes × π×100² × 3.58 m thickness) — within 7%
  of the PRD figure.
- tonnage ≈ **3.9M t** (× 3.5 t/m³) — within 7% of the PRD figure.
- grade ≈ **43.8%** vs PRD 32% — **documented discrepancy**: the Phase 5/6
  synthetic ground truth was designed with richer ore (~44% Mn) per
  docs/synthetic_data_assumptions.md §9.4, which already flagged that
  "Phase 13 must reconcile actual sampled means against PRD figures and
  document any gap." This is that reconciliation: the PRD's 32% is
  illustrative; 43.8% is this build's honest output.
- contained Mn ≈ **1.72M t** vs PRD 1.34M t — flows directly from the grade
  difference.

Decision: **the pipeline's numbers are the real output of this build**; the
PRD figures are illustrative targets. Volume/tonnage land close; grade and
contained Mn differ because the synthetic ore is richer — documented, not
silently forced.

## Files

- `estimate.py` — pure estimation functions (testable)
- `backend/app/services/resource_estimation_service.py` — serving layer
- `backend/app/api/resource_estimation.py` — endpoints
