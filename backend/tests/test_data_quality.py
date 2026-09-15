"""Unit tests for data quality checks (PRD Section 41)."""

from datetime import date, timedelta

from app.core.data_quality import check_dataset_health


def test_missing_dataset_flagged():
    report = check_dataset_health(datasets=["weather"])
    assert report.ok is False
    assert len(report.flags) == 1
    flag = report.flags[0]
    assert flag.dataset == "weather"
    assert flag.kind == "missing"
    assert "not been ingested" in flag.detail


def test_stale_dataset_flagged():
    ref = date(2026, 8, 27)
    report = check_dataset_health(
        datasets=["weather"],
        row_counts={"weather": 100},
        latest_dates={"weather": {"B3": ref - timedelta(days=30)}},
        reference_date=ref,
        zones=["B3"],
    )
    assert report.ok is False
    assert len(report.flags) == 1
    flag = report.flags[0]
    assert flag.dataset == "weather"
    assert flag.zone == "B3"
    assert flag.kind == "stale"
    assert "30 days ago" in flag.detail
    assert "threshold 7" in flag.detail


def test_recent_data_passes():
    ref = date(2026, 8, 27)
    report = check_dataset_health(
        datasets=["weather"],
        row_counts={"weather": 100},
        latest_dates={"weather": {"B3": ref - timedelta(days=1)}},
        reference_date=ref,
        zones=["B3"],
    )
    assert report.ok is True
    assert report.flags == []


def test_empty_dataset_flagged_unreliable_for_equipment():
    report = check_dataset_health(datasets=["equipment"], row_counts={"equipment": 0})
    assert report.ok is False
    flag = report.flags[0]
    assert flag.kind == "unreliable"
    assert "zero rows" in flag.detail


def test_missing_zone_data_flagged():
    ref = date(2026, 8, 27)
    report = check_dataset_health(
        datasets=["weather"],
        row_counts={"weather": 100},
        latest_dates={"weather": {"B3": ref - timedelta(days=1)}},
        reference_date=ref,
        zones=["B3", "C4"],
    )
    assert report.ok is False
    kinds = {(f.dataset, f.zone, f.kind) for f in report.flags}
    assert ("weather", "C4", "missing") in kinds
    assert ("weather", "B3", "stale") not in kinds
