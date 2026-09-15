# Reserve Prospectivity Model — Evaluation Report (Phase 12)

- Model: random_forest (version v1)
- Zones: 20 (small synthetic sample — metrics are indicative only)
- Label strategy: proxy (cluster OR mn>=35 AND holes>=4) (see README.md for the honest proxy-label caveat)
- CV folds: 4 (4 positive labels — one per fold; 5 folds would give single-class folds)
- Calibration: temperature-scaled sigmoid (target positive mean 0.90) (temperature 0.19220554198156545)

## Cross-validated metrics (4-fold stratified)

| Metric | Value |
| --- | --- |
| Precision | 1.000 |
| Recall | 1.000 |
| ROC-AUC | 1.000 |

> With n=20, these numbers are honest but noisy. The spatial ranking
> check below is the primary face-validity signal for this prototype.

## Spatial ranking sanity check

| Check | Value |
| --- | --- |
| Cluster (B2/B3/C2/C3) mean score | 93.0% |
| Known-low zones mean score | 7.4% |
| Cluster ranks above low zones | True |
| Top cluster zone | B2 |

## Zone scores (deployed model, in-sample)

| Zone | Prospectivity |
| --- | --- |
| B2 | 93.1% |
| B3 | 93.1% |
| C3 | 92.9% |
| C2 | 92.8% |
| A4 | 9.1% |
| D1 | 8.2% |
| D2 | 8.2% |
| C4 | 7.6% |
| A1 | 7.2% |
| A2 | 7.2% |
| D5 | 7.2% |
| D4 | 7.1% |
| B1 | 7.0% |
| B4 | 7.0% |
| C1 | 7.0% |
| A3 | 6.9% |
| A5 | 6.9% |
| B5 | 6.9% |
| C5 | 6.9% |
| D3 | 6.9% |
