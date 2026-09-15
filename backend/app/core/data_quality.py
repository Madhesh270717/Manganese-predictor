"""Data quality checks — PRD Section 41 (Non-Functional Requirements).

Pure functions: no DB access. Ingestion and API phases feed in the facts
(latest date per dataset/zone, row counts) and get back structured flags.
Unit-testable without a database.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

DEFAULT_STALE_DAYS: dict[str, int] = {
    "weather": 7,
    "satellite": 16,
    "production": 3,
    "blasting": 7,
    "mining_schedule": 1,
    "geological": 30,
    "geochemical": 30,
    "exploration": 30,
    "equipment": 30,
}

DatasetRowCounts = dict[str, int]
DatasetLatestDates = dict[str, dict[str, date]]


@dataclass
class DataQualityIssue:
    dataset: str
    zone: str | None
    kind: str  # "missing" | "stale" | "unreliable"
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"dataset": self.dataset, "zone": self.zone, "kind": self.kind, "detail": self.detail}


@dataclass
class DataQualityReport:
    flags: list[DataQualityIssue] = field(default_factory=list)
    ok: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "flags": [f.as_dict() for f in self.flags]}


def _classify_issue(dataset: str) -> str:
    return "unreliable" if dataset in {"equipment", "production"} else "missing"


def check_dataset_health(
    *,
    datasets: list[str],
    row_counts: DatasetRowCounts | None = None,
    latest_dates: DatasetLatestDates | None = None,
    reference_date: date | None = None,
    stale_days: dict[str, int] | None = None,
    zones: list[str] | None = None,
) -> DataQualityReport:
    """Flag datasets that are missing, empty, or stale.

    Args:
        datasets: dataset categories to check (keys of row_counts/latest_dates).
        row_counts: number of rows per dataset (omitted key == not loaded yet).
        latest_dates: latest observation date per dataset per zone.
        reference_date: "now" for staleness math (defaults to today, UTC).
        stale_days: per-dataset staleness thresholds (defaults above).
        zones: zone ids to check per-dataset freshness; if None, only dataset-level checks run.
    """
    row_counts = row_counts or {}
    latest_dates = latest_dates or {}
    reference_date = reference_date or datetime.now().date()
    thresholds = {**DEFAULT_STALE_DAYS, **(stale_days or {})}
    report = DataQualityReport()

    for dataset in datasets:
        count = row_counts.get(dataset)
        if count is None:
            report.flags.append(
                DataQualityIssue(dataset, None, "missing", f"{dataset} has not been ingested yet")
            )
            report.ok = False
            continue
        if count == 0:
            report.flags.append(
                DataQualityIssue(dataset, None, _classify_issue(dataset), f"{dataset} has zero rows")
            )
            report.ok = False
            continue

        threshold = thresholds.get(dataset)
        if threshold is None or latest_dates.get(dataset) is None:
            continue

        if zones:
            for zone in zones:
                last = latest_dates[dataset].get(zone)
                if last is None:
                    report.flags.append(
                        DataQualityIssue(
                            dataset, zone, "missing", f"{dataset} has no rows for zone {zone}"
                        )
                    )
                    report.ok = False
                elif reference_date - last > timedelta(days=threshold):
                    report.flags.append(
                        DataQualityIssue(
                            dataset,
                            zone,
                            "stale",
                            f"{dataset} for zone {zone} last seen {last.isoformat()} "
                            f"({(reference_date - last).days} days ago, threshold {threshold})",
                        )
                    )
                    report.ok = False
        else:
            for zone, last in latest_dates[dataset].items():
                if reference_date - last > timedelta(days=threshold):
                    report.flags.append(
                        DataQualityIssue(
                            dataset,
                            zone,
                            "stale",
                            f"{dataset} for zone {zone} last seen {last.isoformat()} "
                            f"({(reference_date - last).days} days ago, threshold {threshold})",
                        )
                    )
                    report.ok = False

    return report
