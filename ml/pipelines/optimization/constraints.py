"""Schedule constraints — Phase 18 (PRD Section 22).

Each constraint is a checkable function returning (is_valid, reason).
Context (equipment fleet, weather, terrain, blasting) is injected so the
functions stay pure and testable. Constraint kinds documented here:

1. equipment_exclusivity  HARD — one unit, one zone per shift
2. maintenance            HARD — units with availability below threshold
                          (in maintenance) cannot be scheduled
3. blasting_sequencing    HARD — excavation must follow completed blasting
4. haulage_capacity       HARD — scheduled haulage ≤ truck capacity
5. weather_restriction    SOFT — high-rain zones flagged as warnings, not
                          hard-blocked (weather is transient; blocking
                          would be over-constraining — documented decision)
6. accessibility          SOFT — long inter-zone moves flag a travel-time
                          warning (movement feasibility is advisory here)
"""

from __future__ import annotations

from datetime import date

from ml.pipelines.optimization.schedule_model import CandidateSchedule

MAINTENANCE_AVAILABILITY_THRESHOLD = 0.25  # below this = in maintenance
WEATHER_RESTRICTED_MM = 60.0  # PRD §8/Phase 8 risk-alert threshold
MAX_MOVE_HAUL_KM = 12.0  # beyond this, inter-zone moves are flagged


def check_equipment_exclusivity(schedule: CandidateSchedule) -> tuple[bool, str]:
    """An equipment unit cannot be assigned to two zones in the same shift."""
    seen: dict[tuple[str, date, str], str] = {}
    for entry in schedule.entries:
        key = (entry.equipment_id, entry.date, entry.shift)
        if key in seen and seen[key] != entry.zone_id:
            return False, (
                f"{entry.equipment_id} double-booked on {entry.date} shift {entry.shift}: "
                f"zones {seen[key]} and {entry.zone_id}"
            )
        seen[key] = entry.zone_id
    return True, ""


def check_maintenance(
    schedule: CandidateSchedule,
    availability_by_equipment: dict[str, float] | None = None,
) -> tuple[bool, str]:
    """Units in maintenance (availability < threshold) cannot be scheduled."""
    availability_by_equipment = availability_by_equipment or {}
    for entry in schedule.entries:
        avail = availability_by_equipment.get(entry.equipment_id)
        if avail is not None and avail < MAINTENANCE_AVAILABILITY_THRESHOLD:
            return False, (
                f"{entry.equipment_id} scheduled on {entry.date} but is in maintenance "
                f"(availability {avail:.0%} < {MAINTENANCE_AVAILABILITY_THRESHOLD:.0%})"
            )
    return True, ""


def check_blasting_sequencing(
    schedule: CandidateSchedule,
    blasting_complete_by_zone: dict[str, date] | None = None,
) -> tuple[bool, str]:
    """Excavation cannot precede completed blasting in that zone."""
    blasting_complete_by_zone = blasting_complete_by_zone or {}
    for entry in schedule.entries:
        if entry.operation != "excavation":
            continue
        complete_date = blasting_complete_by_zone.get(entry.zone_id)
        if complete_date is not None and entry.date < complete_date:
            return False, (
                f"excavation in {entry.zone_id} on {entry.date} precedes blasting "
                f"completion {complete_date}"
            )
    return True, ""


def check_haulage_capacity(
    schedule: CandidateSchedule,
    capacity_by_equipment: dict[str, float] | None = None,
) -> tuple[bool, str]:
    """Scheduled haulage per window cannot exceed the assigned trucks' capacity.

    Per-shift check: sum of hauling expected_output vs 12h × capacity of the
    hauling units assigned in that shift.
    """
    capacity_by_equipment = capacity_by_equipment or {}
    per_shift: dict[tuple[date, str], float] = {}
    haulers: dict[tuple[date, str], set[str]] = {}
    for entry in schedule.entries:
        if entry.operation != "hauling":
            continue
        key = (entry.date, entry.shift)
        per_shift[key] = per_shift.get(key, 0.0) + entry.expected_output
        haulers.setdefault(key, set()).add(entry.equipment_id)

    for key, scheduled in per_shift.items():
        capacity = sum(capacity_by_equipment.get(u, 0.0) for u in haulers[key]) * 12
        if capacity <= 0:
            continue
        if scheduled > capacity:
            return False, (
                f"haulage on {key[0]} shift {key[1]}: scheduled {scheduled:.0f}t "
                f"exceeds capacity {capacity:.0f}t"
            )
    return True, ""


def check_weather_restriction(
    schedule: CandidateSchedule,
    rainfall_by_zone: dict[str, float] | None = None,
) -> tuple[bool, list[str]]:
    """SOFT constraint: high-rain zones produce warnings, not hard failures."""
    rainfall_by_zone = rainfall_by_zone or {}
    warnings = []
    for entry in schedule.entries:
        rain = rainfall_by_zone.get(entry.zone_id, 0.0)
        if rain >= WEATHER_RESTRICTED_MM:
            warnings.append(
                f"{entry.zone_id} on {entry.date}: rainfall {rain:.0f}mm >= "
                f"{WEATHER_RESTRICTED_MM:.0f}mm — restricted/deprioritized"
            )
    return (len(warnings) == 0, warnings)


def check_accessibility(
    schedule: CandidateSchedule,
    haul_km_by_zone: dict[str, float] | None = None,
) -> tuple[bool, list[str]]:
    """SOFT constraint: long inter-zone moves flagged as travel warnings."""
    haul_km_by_zone = haul_km_by_zone or {}
    warnings = []
    # Track each unit's consecutive assignments; flag zone changes where the
    # new zone's haul distance is long.
    last_zone: dict[str, str] = {}
    for entry in sorted(schedule.entries, key=lambda e: (e.date, e.shift)):
        prev = last_zone.get(entry.equipment_id)
        if prev is not None and prev != entry.zone_id:
            haul = haul_km_by_zone.get(entry.zone_id)
            if haul is not None and haul > MAX_MOVE_HAUL_KM:
                warnings.append(
                    f"{entry.equipment_id} moves {prev}→{entry.zone_id} on "
                    f"{entry.date}: haul {haul:.1f}km > {MAX_MOVE_HAUL_KM:.0f}km"
                )
        last_zone[entry.equipment_id] = entry.zone_id
    return (len(warnings) == 0, warnings)
