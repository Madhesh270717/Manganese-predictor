# Mineability Scoring — Phase 14 (Module 2, PRD Sections 10–11)

## Design choice: rule-based weighted composite, NOT an ML model

PRD Section 30 does not specify an ML algorithm for Module 2, and the
component factors (terrain, access, weather, equipment) have
operationally-defined meanings where transparent weighting is preferable
to learned weights (PRD Section 41 Explainability). Documented decision:
**weighted-sum with explicit, stable weights**. This also keeps the score
cheap to recompute live, which Dynamic Scheduling (Phase 18+) needs.

## Component scores (0–100 each)

| Component | Logic |
| --- | --- |
| prospectivity | Phase 12 score (already 0–100) |
| resource_availability | Phase 13: NOT_ESTIMATED→20, LOW→55, MEDIUM→80, HIGH→95 |
| terrain | slope: ≤5°→90, ≤12°→75, ≤20°→55, else 35; accessibility POOR −20, MODERATE −8, GOOD −0 |
| access | haul: ≤5km→90, ≤8km→70, ≤12km→55, else 40; road POOR −20, MODERATE −5, GOOD −0 |
| weather | current rainfall (live): 0mm→100, scaled down to 0 at ≥110mm |
| equipment_availability | fleet availability × 100 |

## Composite weights

```
score = 0.20*prospectivity + 0.15*resource + 0.15*terrain
      + 0.10*access + 0.20*weather + 0.20*equipment
```

Weights sum to 1.0. Prospectivity+resource (0.35) anchor the "is there
ore worth mining" question; weather+equipment (0.40) capture the DYNAMIC
operational reality; terrain+access (0.25) capture the static physical
constraints. All weights are constants in score.py — one obvious place to
tune.

## Classification thresholds (PRD Section 11)

| Score | Class | Color |
| --- | --- | --- |
| ≥ 70 | Recommended | green |
| 45–69 | Conditional | yellow |
| < 45 | Avoid-Postpone | red |

## PRD Section 11 example validation target

Zone B: Prospectivity 89, Resource HIGH, Terrain GOOD, Access GOOD,
Weather GOOD, Equipment HIGH → Mineability Score 86%. This build's B3
lands in the same band (see tests); exact match is illustrative.
