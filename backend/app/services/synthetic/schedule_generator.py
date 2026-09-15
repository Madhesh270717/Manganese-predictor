"""Synthetic mining schedule generator — Phase 10.

Generates the CURRENT/ACTIVE shift schedule in the PRD §18/§35 format:
equipment -> zone -> time-block assignments with operation, expected
output, and status.

The deliberate "before" state for the Phase 18–21 optimizer:
- EX-04 (the degraded excavator from Phase 9) is SCHEDULED IN THE AT-RISK
  ZONE A1 for upcoming shifts — the exact assignment the demo will propose
  moving to Zone B.
- EX-05 remains in B3 (the favorable destination), EX-02 in B2, etc.,
  matching each unit's Phase 9 current_zone_id.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.models.enums import ScheduleStatus

# (equipment_id, zone_id, operation, expected_output tonnes/shift)
CURRENT_ASSIGNMENTS: list[tuple[str, str, str, float]] = [
    ("EX-01", "C2", "excavation", 520.0),
    ("EX-02", "B2", "excavation", 490.0),
    ("EX-03", "C3", "excavation", 540.0),
    ("EX-04", "A1", "excavation", 300.0),  # AT-RISK ZONE — the "before" state
    ("EX-05", "B3", "excavation", 560.0),
    ("T-06", "B3", "hauling", 380.0),
    ("T-07", "B2", "hauling", 360.0),
    ("DR-08", "C3", "drilling", 90.0),
    ("DR-09", "B3", "drilling", 95.0),
    ("LD-10", "C2", "loading", 410.0),
]

SHIFTS_PER_DAY = 2
SHIFT_A_START_HOUR = 6
SHIFT_B_START_HOUR = 18


def generate_current_schedule(
    start_date: date | None = None,
    days: int = 7,
) -> list[dict]:
    """Schedule rows for the next `days` days, 2 shifts/day per unit.

    Past-shift rows are 'active' or 'completed' by date; future rows are
    'proposed'. Simpler rule: rows for today and earlier -> 'active',
    tomorrow onward -> 'proposed' (Phase 18 will manage transitions).
    """
    first = start_date or date.today()
    records: list[dict] = []
    for day_offset in range(days):
        d = first + timedelta(days=day_offset)
        for equipment_id, zone_id, operation, expected in CURRENT_ASSIGNMENTS:
            for shift, start_hour in (("A", SHIFT_A_START_HOUR), ("B", SHIFT_B_START_HOUR)):
                start = datetime(
                    d.year, d.month, d.day, start_hour, 0, tzinfo=timezone.utc
                )
                end = start + timedelta(hours=11)
                status = (
                    ScheduleStatus.ACTIVE.value
                    if d <= date.today()
                    else ScheduleStatus.PROPOSED.value
                )
                records.append(
                    {
                        "date": d,
                        "shift": shift,
                        "equipment_id": equipment_id,
                        "zone_id": zone_id,
                        "operation": operation,
                        "planned_start": start,
                        "planned_end": end,
                        "expected_output": expected,
                        "status": status,
                    }
                )
    return records
