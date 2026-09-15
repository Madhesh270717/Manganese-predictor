"""Tests for the optimization foundation — Phase 18."""

from datetime import date, timedelta

import pytest

from ml.pipelines.optimization.schedule_model import (
    CandidateSchedule,
    ScheduleEntry,
)
from ml.pipelines.optimization.validator import validate_schedule
from ml.pipelines.optimization.or_tools_model import build_and_solve
from app.services.production_prediction_service import _current_schedule


def _entry(equipment, zone, day_offset=0, shift="A", operation="excavation", output=300.0):
    return ScheduleEntry(
        date=date.today() + timedelta(days=day_offset),
        shift=shift,
        equipment_id=equipment,
        zone_id=zone,
        operation=operation,
        expected_output=output,
    )


def test_equipment_exclusivity_violation():
    schedule = CandidateSchedule(
        entries=[
            _entry("EX-04", "A1"),
            _entry("EX-04", "B3"),  # same unit, same shift, different zone
        ]
    )
    report = validate_schedule(schedule)
    assert report["valid"] is False
    assert any(v["constraint"] == "equipment_exclusivity" for v in report["violations"])


def test_maintenance_violation():
    schedule = CandidateSchedule(entries=[_entry("EX-04", "A1")])
    report = validate_schedule(
        schedule,
        context={"availability_by_equipment": {"EX-04": 0.15}},  # in maintenance
    )
    assert report["valid"] is False
    assert any(v["constraint"] == "maintenance" for v in report["violations"])


def test_blasting_sequencing_violation():
    schedule = CandidateSchedule(entries=[_entry("EX-04", "A1", operation="excavation")])
    report = validate_schedule(
        schedule,
        context={"blasting_complete_by_zone": {"A1": date.today() + timedelta(days=1)}},
    )
    assert report["valid"] is False
    assert any(v["constraint"] == "blasting_sequencing" for v in report["violations"])


def test_haulage_capacity_violation():
    schedule = CandidateSchedule(
        entries=[
            _entry("T-06", "B3", operation="hauling", output=5000.0),
        ]
    )
    report = validate_schedule(
        schedule,
        context={"capacity_by_equipment": {"T-06": 60.0}},  # 60t/h × 12h = 720t
    )
    assert report["valid"] is False
    assert any(v["constraint"] == "haulage_capacity" for v in report["violations"])


def test_weather_soft_warning():
    schedule = CandidateSchedule(entries=[_entry("EX-04", "A1")])
    report = validate_schedule(
        schedule,
        context={"rainfall_by_zone": {"A1": 110.0}},
    )
    assert report["valid"] is True  # soft — no hard failure
    assert any(w["constraint"] == "weather_restriction" for w in report["warnings"])


def test_accessibility_soft_warning():
    schedule = CandidateSchedule(
        entries=[_entry("EX-04", "A1", day_offset=0), _entry("EX-04", "D5", day_offset=1)]
    )
    report = validate_schedule(
        schedule,
        context={"haul_km_by_zone": {"D5": 15.0}},
    )
    assert report["valid"] is True
    assert any(w["constraint"] == "accessibility" for w in report["warnings"])


def test_current_schedule_is_valid():
    """The Phase 10 current schedule must pass all hard constraints."""
    dicts = _current_schedule()
    schedule = CandidateSchedule.from_dicts(dicts)
    report = validate_schedule(schedule)
    assert report["valid"] is True, report["violations"]
    assert report["entries_checked"] == len(dicts)


def test_or_tools_solves_current_schedule():
    dicts = _current_schedule()
    schedule = CandidateSchedule.from_dicts(dicts)
    result = build_and_solve(schedule)
    assert result["feasible"] is True
    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    assert result["assignments"] == len(dicts)


def test_or_tools_detects_double_booking():
    schedule = CandidateSchedule(
        entries=[_entry("EX-04", "A1"), _entry("EX-04", "B3")]
    )
    result = build_and_solve(schedule)
    assert result["feasible"] is False
    assert result["status"] == "INFEASIBLE"
