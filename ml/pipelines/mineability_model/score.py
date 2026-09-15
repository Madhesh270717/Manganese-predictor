"""Mineability scoring — Phase 14 (Module 2).

Pure scoring functions with documented weights/thresholds (README.md).
Takes live component values as inputs so the service can recompute on
every request — mineability is DYNAMIC (weather/equipment change).
"""

from __future__ import annotations

WEIGHTS = {
    "prospectivity": 0.20,
    "resource_availability": 0.15,
    "terrain": 0.15,
    "access": 0.10,
    "weather": 0.20,
    "equipment_availability": 0.20,
}

RECOMMENDED_THRESHOLD = 70.0
CONDITIONAL_THRESHOLD = 45.0


def classify(score: float) -> str:
    if score >= RECOMMENDED_THRESHOLD:
        return "Recommended"
    if score >= CONDITIONAL_THRESHOLD:
        return "Conditional"
    return "Avoid-Postpone"


def color(classification: str) -> str:
    return {
        "Recommended": "green",
        "Conditional": "yellow",
        "Avoid-Postpone": "red",
    }[classification]


def resource_tier_score(resource_confidence: str) -> float:
    return {
        "NOT_ESTIMATED": 20.0,
        "LOW": 55.0,
        "MEDIUM": 80.0,
        "HIGH": 95.0,
    }.get(resource_confidence, 20.0)


def terrain_score(slope_degrees: float | None, accessibility: str | None) -> float:
    if slope_degrees is None:
        base = 50.0
    elif slope_degrees <= 5:
        base = 90.0
    elif slope_degrees <= 12:
        base = 75.0
    elif slope_degrees <= 20:
        base = 55.0
    else:
        base = 35.0

    base += {"GOOD": 0, "MODERATE": -8, "POOR": -20}.get(accessibility or "POOR", -20)
    return max(0.0, min(100.0, base))


def access_score(haul_km: float | None, road_condition: str | None) -> float:
    if haul_km is None:
        base = 50.0
    elif haul_km <= 5:
        base = 90.0
    elif haul_km <= 8:
        base = 70.0
    elif haul_km <= 12:
        base = 55.0
    else:
        base = 40.0

    base += {"GOOD": 0, "MODERATE": -5, "POOR": -20}.get(road_condition or "POOR", -20)
    return max(0.0, min(100.0, base))


def weather_score(rainfall_1d: float | None) -> float:
    """Current rainfall: 0mm → 100, linearly down to 0 at ≥110mm (PRD spike)."""
    if rainfall_1d is None:
        return 50.0
    return max(0.0, min(100.0, 100.0 - (rainfall_1d / 110.0) * 100.0))


def equipment_score(fleet_availability: float | None) -> float:
    if fleet_availability is None:
        return 50.0
    return max(0.0, min(100.0, fleet_availability * 100.0))


def composite_score(
    *,
    prospectivity: float,
    resource_confidence: str,
    slope_degrees: float | None,
    accessibility: str | None,
    haul_km: float | None,
    road_condition: str | None,
    rainfall_1d: float | None,
    fleet_availability: float | None,
) -> dict:
    """Full component breakdown + weighted composite (0–100)."""
    components = {
        "prospectivity": prospectivity,
        "resource_availability": resource_tier_score(resource_confidence),
        "terrain": terrain_score(slope_degrees, accessibility),
        "access": access_score(haul_km, road_condition),
        "weather": weather_score(rainfall_1d),
        "equipment_availability": equipment_score(fleet_availability),
    }

    score = sum(WEIGHTS[key] * value for key, value in components.items())
    classification = classify(score)

    return {
        "components": {k: round(v, 1) for k, v in components.items()},
        "weights": WEIGHTS,
        "mineability_score": round(score, 1),
        "classification": classification,
        "color": color(classification),
    }
