"""Unified schedule representation — Phase 18 (Module 4).

ONE candidate-schedule structure used by the optimizer, the validator,
the CP-SAT model, and Phase 15's predict_production()/scenario endpoints.

Canonical entry fields:
    date            (date)
    shift           ('A' | 'B')
    equipment_id    (str, PRD id like EX-04)
    zone_id         (str, like B3)
    operation       (str: excavation/hauling/drilling/loading)
    expected_output (float, tonnes for this assignment)

`start_time`/`end_time` are DERIVED (shift A = 06:00–17:00, shift B =
18:00–05:00) — storing them invites inconsistency; the validator computes
them from date+shift via helpers here. Phase 15's POST /scenario already
accepts exactly these fields minus start/end, so this is the reconciled
single representation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

SHIFT_START_HOUR = {"A": 6, "B": 18}
SHIFT_DURATION_HOURS = 11


@dataclass
class ScheduleEntry:
    date: date
    shift: str
    equipment_id: str
    zone_id: str
    operation: str
    expected_output: float

    @property
    def start_time(self) -> datetime:
        hour = SHIFT_START_HOUR[self.shift]
        return datetime(self.date.year, self.date.month, self.date.day, hour, 0, tzinfo=timezone.utc)

    @property
    def end_time(self) -> datetime:
        return self.start_time + timedelta(hours=SHIFT_DURATION_HOURS)

    def overlaps(self, other: "ScheduleEntry") -> bool:
        return self.start_time < other.end_time and other.start_time < self.end_time

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "shift": self.shift,
            "equipment_id": self.equipment_id,
            "zone_id": self.zone_id,
            "operation": self.operation,
            "expected_output": self.expected_output,
        }


@dataclass
class CandidateSchedule:
    entries: list[ScheduleEntry] = field(default_factory=list)

    def to_dicts(self) -> list[dict]:
        return [e.to_dict() for e in self.entries]

    @classmethod
    def from_dicts(cls, dicts: list[dict]) -> "CandidateSchedule":
        return cls(
            entries=[
                ScheduleEntry(
                    date=e["date"],
                    shift=e["shift"],
                    equipment_id=e["equipment_id"],
                    zone_id=e["zone_id"],
                    operation=e.get("operation", "excavation"),
                    expected_output=e["expected_output"],
                )
                for e in dicts
            ]
        )

    def by_equipment(self) -> dict[str, list[ScheduleEntry]]:
        out: dict[str, list[ScheduleEntry]] = {}
        for entry in self.entries:
            out.setdefault(entry.equipment_id, []).append(entry)
        return out

    def by_zone_date(self) -> dict[tuple[str, date], list[ScheduleEntry]]:
        out: dict[tuple[str, date], list[ScheduleEntry]] = {}
        for entry in self.entries:
            out.setdefault((entry.zone_id, entry.date), []).append(entry)
        return out
