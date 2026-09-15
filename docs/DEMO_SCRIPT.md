# Spotter AI — MVP Demo Script (PRD Section 44)

The 12-step presentation runbook for the Smart India Hackathon demo. Every
step shows a real screen powered by real backend calls — nothing is scripted
text. Steps 1–2 and 9–10 use the platform's actual computed numbers, which
are documented where they differ from the PRD's illustrative figures.

> **Demo reset**: before starting, run `python -m app.core.reset_demo_scenario`
> from `backend/` to restore the pre-demo state (clears any accepted
> recommendation, re-applies the A1 rainfall trigger). See docs/DEPLOYMENT.md.

---

## STEP 1 — Spotter AI identifies Zone B: Mn prospectivity 91%
**Screen:** 2 — Reserve Map (`/reserve-map`)
**What to show:** the 20-cell zone grid colored by prospectivity. Point at
the B-row cluster (B2/B3/C2/C3) — high prospectivity in green.
**What to say:** "Spotter AI's reserve model ranks the B-cluster as the most
prospective manganese ground. Zone B3 scores high on ore-access indicators."
**Backend:** `GET /api/v1/reserve/prospectivity` (Phase 12 model).

*Real numbers (this build): B3 = 93.1%, B2 = 93.1%, C3 = 92.9%, C2 = 92.8%.
The PRD's "91%" is illustrative; the model's real output is ~93%.*

## STEP 2 — Resource model: estimated ore ~4.2 Mt
**Screen:** 2 — Reserve Map, click **B3** (zone detail panel)
**What to show:** the detail panel's Resource Estimate block.
**What to say:** "Drilling-backed statistical estimation: B3 holds roughly
3.9 Mt of ore at ~43.8% Mn — a MEDIUM confidence estimate, not a certified
reserve."
**Backend:** `GET /api/v1/reserve/resource-estimate/B3` (Phase 13).

*Real numbers: 3.93 Mt ore / 1.12 M m³ / 43.8% Mn / 1.72 Mt contained Mn.
The PRD's "4.2 Mt at 32%" is the illustrative target; volume/tonnage land
within 7%, grade differs because the synthetic ore body is richer
(document gap in ml/pipelines/resource_estimation/README.md).*

## STEP 3 — Zone A is currently scheduled
**Screen:** 5 — Dynamic Schedule (`/schedule`)
**What to show:** the Current Assignments table — EX-04 row is highlighted
(red) in zone A1.
**What to say:** "Today's plan puts excavator EX-04 in Zone A."
**Backend:** `GET /api/v1/schedule/current` (Phase 10).

## STEP 4 — Weather system detects heavy rainfall in Zone A
**Screen:** 4 — Risk Analysis (`/risk-analysis`), Weather Risk Alerts card
**What to show:** the A1 alert — rainfall_1d 110mm, trigger rainfall_1d.
**What to say:** "The weather feed flags 110 mm of rainfall in Zone A — over
the 60 mm risk threshold."
**Backend:** `GET /api/v1/weather/risk-alert` (Phase 8).

## STEP 5 — Production model predicts shortfall
**Screen:** 3 — Production dashboard (`/production`)
**What to show:** Target / Predicted / Shortfall stat cards + risk bar.
**What to say:** "The production model predicts we'll fall short: target
82,000 t, predicted ~75,000 t — an ~7,000 t shortfall at MEDIUM risk."
**Backend:** `GET /api/v1/production/predict/current` +
`GET /api/v1/production/shortfall/current` (Phases 15–16).

*Real numbers: target 81,994 t, predicted 75,030 t, shortfall 6,964 t (8.5%),
MEDIUM. The PRD's 74,600/7,400 are illustrative; the model's real output is
close (75.0k/7.0k).*

## STEP 6 — AI identifies the causes
**Screen:** 4 — Risk Analysis, Cause Attribution card (SHAP)
**What to show:** the contributor bars — Equipment downtime first, then Ore
grade / Rainfall / Blasting.
**What to say:** "SHAP explains the shortfall: equipment downtime is the
largest driver, with rainfall from the Zone A storm compounding it."
**Backend:** `GET /api/v1/production/shortfall/current/explain` (Phase 17).

*Real numbers: Equipment downtime 65.3%, Ore grade 32.8%, Rainfall 1.9%,
Blasting 0.0% — equipment-first ordering matches the PRD narrative (see
documented deviation in ml/pipelines/production_model/README.md).*

## STEP 7 — Optimization engine evaluates alternatives
**Screen:** 6 — Recommendations (`/recommendations`), Candidate ranking table
**What to show:** the ranked candidate table for EX-04 (C3, B3, C2, B2 with
multi-criteria scores).
**What to say:** "The optimizer evaluates the plausible alternative zones —
B2, B3, C2, C3 — scoring production risk, haul distance, equipment
availability, prospectivity, and the predicted shortfall improvement."
**Backend:** `GET /api/v1/optimization/alternatives/EX-04` (Phase 19).

## STEP 8 — Selects the best zone
**Screen:** 6 — Recommendations, top-ranked row highlighted
**What to show:** C3 ranked #1 (total score 83.7).
**What to say:** "Zone C3 wins on the composite score — close to B3 but with
a shorter haul."
**Backend:** Phase 19 `rank_candidates` (the recommendation's ranking array).

*Documented deviation: the PRD narrative says "Zone B"; the data-driven
ranking is C3 > C2 > B3 > B2 (C3's haul is ~2 km vs B3's ~4.4 km with
near-identical scores). The assistant explains this honestly.*

## STEP 9 — Recommends EX-04: Zone A → Zone B
**Screen:** 6 — Recommendations, the MOVE card
**What to show:** "MOVE EX-04 from A1 → C3", reason "High rainfall predicted
in the current zone", status pending approval.
**What to say:** "The engine recommends moving EX-04 out of the flooded zone
into C3, pending approval — nothing auto-applies."
**Backend:** `GET /api/v1/recommendations/EX-04` (Phase 20).

## STEP 10 — Recalculates: new prediction
**Screen:** 6 — Recommendations, expected-impact boxes
**What to show:** Production 75,030 → 77,960 t; Shortfall 6,964 → 4,034 t.
**What to say:** "Re-running the production model with the move applied shows
production recovering toward target."
**Backend:** Phase 20 `expected_impact` (real before/after model calls).

*Real numbers: +2,930 t production recovered, shortfall cut 42%. The PRD's
81,300 t figure assumes a larger reallocation; the single-move impact is the
honest model output.*

## STEP 11 — Dashboard reflects the improved position
**Screen:** 6 — Recommendations, "Accept & Apply" → 3 — Production / 1 —
Overview
**What to show:** click **Accept & Apply**, then navigate to Production —
the shortfall shown reflects the accepted move.
**What to say:** "With the recommendation approved, the dashboard reflects
the improved production position. The demo can be reset at any time to run
again."
**Backend:** `POST /api/v1/demo/accept` (Phase 30 demo-state),
`GET /api/v1/metrics/summary` scheduling-impact block (Phase 30).

## STEP 12 — Spotter AI explains the decision
**Screen:** 7 — Assistant (`/assistant`)
**What to show/type:** ask "Why should we leave Zone A?"
**What to say:** "Spotter AI ties it together in plain language — grounded in
the same model results we just walked through."
**Expected answer:** "Regarding why A1 was postponed: A1 currently has a HIGH
risk trigger: weather rainfall_1d 110mm ≥ 60mm; mineability is 32.1
(Avoid-Postpone). The recommended action is to move EX-04 from A1 to C3."
**Backend:** `POST /api/v1/assistant/chat` (Phase 29, grounded tool-use).

---

## Repeatable runs

After the demo, restore the pre-run state:

```bash
cd backend
python -m app.core.reset_demo_scenario     # clears accept + re-applies weather trigger
```

The 12 steps can then be replayed from Step 1.
