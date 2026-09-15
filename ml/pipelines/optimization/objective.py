"""Formal optimization objective — Phase 20 (PRD Section 23).

BEST SCHEDULE = Maximum Production + Maximum Equipment Utilization
                − Operational Risk − Equipment Movement − Expected Shortfall

Five terms on incompatible scales (tonnes, %, km), so each is normalized
to 0–100 before weighting — documented per term:

  production_score  = predicted / target × 100        (cap 100)
  utilization_score = mean fleet availability × 100
  risk_score        = mean operational risk × 100     (risk = 100 − mineability)
  movement_penalty  = total move km / 20 km × 100
  shortfall_penalty = shortfall % / 15% × 100         (15% = HIGH boundary)

Weights (sum 1.0): production 0.30, utilization 0.20, risk 0.20,
movement 0.10, shortfall 0.20. Total is a comparable composite where
higher is better.

objective.score_schedule() is the CANONICAL evaluator — the CP-SAT model
uses a linearized per-assignment proxy consistent with these terms, and
the recommendation engine scores candidate schedules with this function.
"""

from __future__ import annotations

WEIGHTS = {
    "production": 0.30,
    "utilization": 0.20,
    "risk": 0.20,
    "movement": 0.10,
    "shortfall": 0.20,
}

NORM_MOVEMENT_KM = 20.0  # 20 km of moves = full movement penalty
NORM_SHORTFALL_PCT = 15.0  # 15% shortfall (HIGH boundary) = full penalty


def production_score(predicted: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return min(100.0, predicted / target * 100.0)


def utilization_score(mean_availability: float) -> float:
    return max(0.0, min(100.0, mean_availability * 100.0))


def risk_score(mineability_scores: list[float]) -> float:
    """Operational risk = 100 − average mineability (higher risk = worse)."""
    if not mineability_scores:
        return 50.0
    avg = sum(mineability_scores) / len(mineability_scores)
    return max(0.0, min(100.0, 100.0 - avg))


def movement_penalty(total_move_km: float) -> float:
    return max(0.0, min(100.0, total_move_km / NORM_MOVEMENT_KM * 100.0))


def shortfall_penalty(shortfall_percentage: float) -> float:
    return max(0.0, min(100.0, shortfall_percentage / NORM_SHORTFALL_PCT * 100.0))


def score_schedule(
    *,
    predicted_tonnes: float,
    target_tonnes: float,
    mean_availability: float,
    mineability_scores: list[float],
    total_move_km: float,
    shortfall_percentage: float,
) -> dict:
    """Full PRD §23 composite score with per-term breakdown."""
    terms = {
        "production": production_score(predicted_tonnes, target_tonnes),
        "utilization": utilization_score(mean_availability),
        "risk": risk_score(mineability_scores),
        "movement": movement_penalty(total_move_km),
        "shortfall": shortfall_penalty(shortfall_percentage),
    }

    total = (
        WEIGHTS["production"] * terms["production"]
        + WEIGHTS["utilization"] * terms["utilization"]
        - WEIGHTS["risk"] * terms["risk"]
        - WEIGHTS["movement"] * terms["movement"]
        - WEIGHTS["shortfall"] * terms["shortfall"]
    )

    return {
        "terms": {k: round(v, 1) for k, v in terms.items()},
        "weights": WEIGHTS,
        "objective_score": round(total, 1),
    }
