# Reserve Prospectivity Model — Phase 12

## What this model is

A **statistical prospectivity classifier** (Random Forest + XGBoost, per PRD
Section 30). Given one feature row per zone (Phase 11), it outputs a
probability 0–100% and a classification (LOW / MEDIUM / HIGH).

**This is NOT a certified geological reserve** (PRD Section 8). It is a
model-inferred prospectivity score. Every API response carries
`data_type: "statistical_prospectivity"` to enforce the distinction, and the
service layer refuses to output tonnage/volume language.

## Label strategy (proxy labels — honest prototype limitation)

No historical discovery/assay dataset exists to serve as ground truth, so
labels are derived from a **documented proxy** that combines the Phase 5
ground-truth cluster with independent signal strength:

```
label = HIGH (1)  if:
    zone in HIGH_PROSPECTIVITY_ZONES (B2/B3/C2/C3)          # documented truth
    OR (mn_concentration >= 35 AND drill_hole_count >= 4)    # geochemical+drilling evidence
else LOW (0)
```

Why this is defensible and not fully circular:

- The label uses the Phase 5 *cluster membership* (a coarse spatial prior)
  plus *evidence-strength thresholds* on Phase 5/6 outputs.
- The model's FEATURES include many fields the label never sees directly:
  fault/lineament distance, lithology encoding, satellite NDVI/LST/soil
  moisture, iron-oxide ratio, trace elements, drilling depth/thickness.
- Cross-validation on n=20 is used (no holdout), so the model is evaluated
  on how well it generalizes the feature->label mapping, not on memorizing
  the cluster constant itself.

**In a real deployment**, labels would come from confirmed historical
discoveries, assay-verified resources, or expert review. This prototype
substitutes the documented proxy above; that limitation must be stated in
any downstream claim (PRD Section 39 confidence tagging applies).

## Classification thresholds (PRD Sections 6–9)

| Score | Class | Color (PRD §7) |
| --- | --- | --- |
| < 40% | LOW | green |
| 40–70% | MEDIUM | yellow |
| ≥ 70% | HIGH | red |

Thresholds live in `backend/app/services/reserve_model_service.py` so the
API and any UI consume the same cutoffs.

## Training (small-n discipline)

- **n = 20 zones** — a single holdout split is statistically meaningless, so
  both models are evaluated with **5-fold stratified cross-validation**.
- Model selection: the better mean ROC-AUC across folds is saved as the
  artifact; the comparison is recorded in evaluation_report.md.
- Artifacts: `ml/pipelines/reserve_model/artifacts/` (joblib).

## Files

- `train.py` — label construction, CV training, artifact save
- `evaluate.py` — precision/recall/ROC-AUC + spatial ranking sanity check,
  writes `evaluation_report.md`
- `backend/app/services/reserve_model_service.py` — prediction service
- `backend/app/api/reserve_model.py` — prospectivity endpoints
