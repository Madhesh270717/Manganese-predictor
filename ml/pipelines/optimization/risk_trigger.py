"""Risk trigger detection — Phase 19 (PRD Section 19).

Determines when re-evaluation/reallocation should happen. Triggers:

(a) a scheduled zone shows HIGH weather risk (Phase 8 threshold:
    rainfall_1d >= 60mm or rainfall_7d >= 150mm), OR
(b) the current schedule's shortfall risk (Phase 16) is MEDIUM or HIGH.

Returns one entry per at-risk equipment assignment with an explainable
reason — the input the candidate evaluation (zone_comparator) consumes.
"""

from __future__ import annotations

from app.services.shortfall_service import get_current_shortfall

WEATHER_HIGH_1D = 60.0
WEATHER_HIGH_7D = 150.0


def detect_schedule_risks(current_schedule: list[dict]) -> list[dict]:
    """Detect risk triggers for the current schedule.

    Args:
        current_schedule: Phase 15-format schedule entries.

    Returns:
        [{equipment_id, current_zone_id, risk_reason, severity}, ...]
        severity: HIGH (weather trigger or HIGH shortfall) / MEDIUM.
    """
    from app.services.production_prediction_service import _current_rainfall

    rainfall = _current_rainfall()

    # Shortfall trigger (mine-level per Phase 16).
    shortfall = get_current_shortfall()
    shortfall_risk = shortfall.get("risk_level")
    shortfall_triggered = shortfall_risk in ("MEDIUM", "HIGH")

    triggers: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for entry in current_schedule:
        zone = entry["zone_id"]
        key = (entry["equipment_id"], zone)
        if key in seen:
            continue

        rain_1d = rainfall.get(zone, 0.0)
        rain_7d = rain_1d * 3.0  # demo storm approximation (documented)
        weather_high = rain_1d >= WEATHER_HIGH_1D or rain_7d >= WEATHER_HIGH_7D

        if weather_high:
            seen.add(key)
            triggers.append(
                {
                    "equipment_id": entry["equipment_id"],
                    "current_zone_id": zone,
                    "risk_reason": f"weather: rainfall_1d {rain_1d:.0f}mm >= {WEATHER_HIGH_1D:.0f}mm",
                    "severity": "HIGH",
                }
            )
        elif shortfall_triggered:
            seen.add(key)
            triggers.append(
                {
                    "equipment_id": entry["equipment_id"],
                    "current_zone_id": zone,
                    "risk_reason": f"shortfall risk {shortfall_risk} "
                                   f"({shortfall.get('shortfall_percentage', 0):.1f}%)",
                    "severity": shortfall_risk,
                }
            )

    return triggers
