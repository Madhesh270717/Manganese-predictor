"""Multi-criteria zone comparator — Phase 19 (PRD Section 19 diagram).

PRD §19 evaluates alternatives along three axes: Production Risk, Distance,
Equipment — plus this phase adds the decisive SHORTFALL DELTA (Phase 15/16
reuse) and the destination PROSPECTIVITY the PRD shows in its decision
context. Five documented criteria:

Scores (0–100, documented weights):
    production_risk   0.25  — weather risk inverse (100 = no risk) +
                              mineability score average
    distance          0.15  — haul km inverse
    equipment         0.15  — fleet availability at destination
    prospectivity     0.15  — destination Mn prospectivity (PRD §19 context)
    shortfall_delta   0.30  — predicted shortfall improvement vs current
"""

from __future__ import annotations


def _weather_score(zone_id: str) -> float:
    from app.services.mineability_service import _current_weather

    rain = _current_weather(zone_id) or 0.0
    return max(0.0, 100.0 - rain)  # 110mm → 0, dry → 100


def _prospectivity_score(zone_id: str) -> float:
    from app.services.reserve_model_service import get_prospectivity

    result = get_prospectivity(zone_id)
    return result["prospectivity_score"] if result else 0.0


def _distance_score(zone_id: str) -> float:
    from app.services.mineability_service import _terrain_by_zone

    haul = _terrain_by_zone().get(zone_id, {}).get("haul_km")
    if haul is None:
        return 50.0
    return max(0.0, 100.0 - haul * 8.0)  # 0km → 100, 12km → 4


def _equipment_score(zone_id: str) -> float:
    from app.services.mineability_service import _current_fleet_availability

    avail = _current_fleet_availability(zone_id)
    return (avail or 0.5) * 100.0


def _shortfall_delta_score(
    equipment_id: str,
    candidate_zone_id: str,
    current_schedule: list[dict],
) -> float:
    """Shortfall reduction if the unit moved to the candidate zone.

    Reuses Phase 15's hypothetical prediction + Phase 16's shortfall —
    exactly the before/after comparison the Phase 20 optimizer needs.
    """
    from app.services.shortfall_service import get_current_shortfall, get_scenario_shortfall

    baseline = get_current_shortfall()["shortfall_tonnes"]

    scenario = [dict(e) for e in current_schedule]
    for entry in scenario:
        if entry["equipment_id"] == equipment_id:
            entry["zone_id"] = candidate_zone_id

    moved = get_scenario_shortfall(scenario)["shortfall_tonnes"]
    reduction = baseline - moved
    # Map reduction to 0–100: full elimination of a ~7000t shortfall → ~100.
    return max(0.0, min(100.0, 50.0 + reduction / 7000.0 * 50.0))


def evaluate_candidate(
    equipment_id: str,
    candidate_zone_id: str,
    current_schedule: list[dict],
) -> dict:
    """Full multi-criteria evaluation for one candidate zone."""
    from app.services.mineability_service import get_mineability

    mineability = get_mineability(candidate_zone_id) or {}

    criteria = {
        "production_risk": round(
            (_weather_score(candidate_zone_id) + mineability.get("mineability_score", 50.0)) / 2,
            1,
        ),
        "distance": round(_distance_score(candidate_zone_id), 1),
        "equipment": round(_equipment_score(candidate_zone_id), 1),
        "prospectivity": round(_prospectivity_score(candidate_zone_id), 1),
        "shortfall_delta": round(
            _shortfall_delta_score(equipment_id, candidate_zone_id, current_schedule), 1
        ),
    }

    weights = {
        "production_risk": 0.25,
        "distance": 0.15,
        "equipment": 0.15,
        "prospectivity": 0.15,
        "shortfall_delta": 0.30,
    }
    total = sum(weights[k] * v for k, v in criteria.items())

    return {
        "equipment_id": equipment_id,
        "candidate_zone_id": candidate_zone_id,
        "criteria": criteria,
        "weights": weights,
        "total_score": round(total, 1),
        "mineability": {
            "score": mineability.get("mineability_score"),
            "classification": mineability.get("classification"),
        },
    }


def rank_candidates(
    equipment_id: str,
    candidate_zone_ids: list[str],
    current_schedule: list[dict],
) -> list[dict]:
    """Evaluate and rank all candidates by total score desc."""
    results = [
        evaluate_candidate(equipment_id, zone, current_schedule)
        for zone in candidate_zone_ids
    ]
    return sorted(results, key=lambda r: r["total_score"], reverse=True)
