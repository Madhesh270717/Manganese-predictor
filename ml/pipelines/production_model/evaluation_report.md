# Production Prediction Model — Evaluation Report (Phase 15)

- Model: random_forest (version v1)
- Split: time-aware — trained on dates < 2026-06-17, tested on the most recent 365 rows

## Held-out metrics

| Metric | Value |
| --- | --- |
| MAE (t/day) | 25.9 |
| RMSE (t/day) | 33.8 |
| MAPE | 4.7% |

> The test window contains the Phase 8 demo storm (A1 110mm rain),
> so these metrics genuinely reflect the model's ability to predict
> production under the event the demo narrative depends on.

## Top feature importances (high-level)

| Feature | Importance |
| --- | --- |
| planned_production | 0.7462 |
| fleet_capacity | 0.1104 |
| active_units | 0.0823 |
| ore_grade | 0.0399 |
| rainfall_30d | 0.0043 |
