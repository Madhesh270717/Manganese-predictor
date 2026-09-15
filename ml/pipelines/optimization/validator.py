"""Schedule validator — Phase 18.

Runs all six PRD §22 constraint checks against a candidate schedule and
returns a structured validation report. Used by Phase 19–20's schedule
generator to reject invalid candidates before production evaluation.
"""

from __future__ import annotations

from ml.pipelines.optimization.constraints import (
    check_accessibility,
    check_blasting_sequencing,
    check_equipment_exclusivity,
    check_haulage_capacity,
    check_maintenance,
    check_weather_restriction,
)
from ml.pipelines.optimization.schedule_model import CandidateSchedule

HARD_CONSTRAINTS = [
    "equipment_exclusivity",
    "maintenance",
    "blasting_sequencing",
    "haulage_capacity",
]
SOFT_CONSTRAINTS = ["weather_restriction", "accessibility"]


def validate_schedule(
    schedule: CandidateSchedule,
    context: dict | None = None,
) -> dict:
    """Run all constraint checks. Returns a structured report.

    Args:
        schedule: CandidateSchedule to validate.
        context: optional {availability_by_equipment, capacity_by_equipment,
                 blasting_complete_by_zone, rainfall_by_zone, haul_km_by_zone}.
    """
    context = context or {}

    violations: list[dict] = []
    warnings: list[dict] = []

    ok, reason = check_equipment_exclusivity(schedule)
    if not ok:
        violations.append({"constraint": "equipment_exclusivity", "reason": reason})

    ok, reason = check_maintenance(schedule, context.get("availability_by_equipment"))
    if not ok:
        violations.append({"constraint": "maintenance", "reason": reason})

    ok, reason = check_blasting_sequencing(schedule, context.get("blasting_complete_by_zone"))
    if not ok:
        violations.append({"constraint": "blasting_sequencing", "reason": reason})

    ok, reason = check_haulage_capacity(schedule, context.get("capacity_by_equipment"))
    if not ok:
        violations.append({"constraint": "haulage_capacity", "reason": reason})

    ok, items = check_weather_restriction(schedule, context.get("rainfall_by_zone"))
    for item in items:
        warnings.append({"constraint": "weather_restriction", "reason": item})

    ok, items = check_accessibility(schedule, context.get("haul_km_by_zone"))
    for item in items:
        warnings.append({"constraint": "accessibility", "reason": item})

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "hard_constraints": HARD_CONSTRAINTS,
        "soft_constraints": SOFT_CONSTRAINTS,
        "entries_checked": len(schedule.entries),
    }
