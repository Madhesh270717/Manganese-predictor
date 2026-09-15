# Production Prediction Model — Phase 15 (Module 3, PRD Sections 12–16)

## What this model does

Predicts daily actual production (tonnes) per zone from: planned
production, ore grade, equipment fleet availability/downtime/maintenance/
capacity, rainfall (1d/7d/30d), and blasting delays — the Phase 11
`production_features.parquet` table.

## Training discipline: time-aware split (NOT random)

This is time-series data. A random split would leak future patterns into
training, so the split is **temporal**: all rows sorted by date, train on
the earlier 80% of days, evaluate on the most recent 20%. The recent window
contains the Phase 8 demo storm (A1 110mm), so the test set genuinely
measures generalization to the event the demo depends on.

## Models compared (PRD Section 30)

- XGBoost regressor
- Random Forest regressor
- Gradient Boosting regressor

Best test-set RMSE is selected and saved to `artifacts/`. Comparison is
recorded in `evaluation_report.md`. Full SHAP explainability comes in
Phase 17; this phase reports top feature importances only.

## Prediction service: operational adjustment layer (documented)

The trained RF is strong on average (test MAPE 4.7%) but under-learns the
rare heavy-rain events (A1's 110mm storm is ~2% of training rows;
planned_production dominates feature importance). The service therefore
re-applies the **same documented factor rules the Phase 10 generator used**
(synthetic_data_assumptions.md §14.2) post-model:

- weather: rain ≥40mm → ×0.575, 15–40mm → ×0.825
- equipment: ×(0.55 + 0.5 × availability)
- cap: predicted never exceeds planned

This is the physical data-generating mechanism, not a tuned constant —
transparent and §41-explainable. Current-schedule prediction lands at
~75,000t vs the 82,000t target (PRD example: 74,600t) and moves up
sensibly when EX-04 is hypothetically reassigned to Zone B.

## Files

- `train.py` — time-aware split, three regressors, artifact save
- `evaluate.py` — MAE/RMSE/MAPE + report
- `backend/app/services/production_prediction_service.py` — serving +
  hypothetical-schedule prediction (Phase 18+ groundwork)
- `backend/app/api/production_prediction.py` — endpoints
