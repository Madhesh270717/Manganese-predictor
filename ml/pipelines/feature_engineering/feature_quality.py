"""Feature quality checks — Phase 11.

Post-construction validation: % missing per feature, model-usability flags,
and distribution sanity checks. Outputs a report dict (also saved as JSON
by the pipeline runner).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def check_reserve_features(features: pd.DataFrame) -> dict:
    """Quality report for the reserve feature table."""
    issues: list[str] = []

    missing = features.isna().mean().round(4).to_dict()
    high_missing = {k: v for k, v in missing.items() if v > 0.5}
    if high_missing:
        issues.append(f"features with >50% missing: {high_missing}")

    # Distribution sanity: mn_concentration within realistic bounds.
    mn = features["mn_concentration"].dropna()
    if not mn.empty and (mn < 0).any():
        issues.append("negative mn_concentration values present")
    if not mn.empty and mn.max() > 60:
        issues.append(f"mn_concentration above realistic max: {mn.max():.1f}")

    # Drilling missingness flag sanity: flag matches count.
    inconsistent = (
        (features["has_drilling_data"] != (features["drill_hole_count"] > 0)).sum()
    )
    if inconsistent:
        issues.append(f"{inconsistent} zones have has_drilling_data inconsistent with count")

    # Zones with no geological data at all are unusable for Phase 12.
    unusable = features[features["lithology"].isna()]["zone_id"].tolist()
    if unusable:
        issues.append(f"zones missing geological data (unusable for reserve model): {unusable}")

    return {
        "table": "reserve_features",
        "rows": len(features),
        "columns": len(features.columns),
        "missing_pct": missing,
        "issues": issues,
        "ok": not issues,
    }


# Event-sparse features: absence is expected (they have has_* flags) and
# should not trip the generic >50% missing check.
EVENT_SPARSE_COLUMNS = {"blast_delay_same_day", "blast_delay_last_3d"}


def check_production_features(features: pd.DataFrame) -> dict:
    """Quality report for the production feature table."""
    issues: list[str] = []

    missing = features.isna().mean().round(4).to_dict()
    high_missing = {
        k: v
        for k, v in missing.items()
        if v > 0.5 and k not in EVENT_SPARSE_COLUMNS
    }
    if high_missing:
        issues.append(f"features with >50% missing: {high_missing}")

    # Distribution sanity: rainfall and production non-negative.
    for col in ("rainfall_1d", "planned_production", "actual_production"):
        values = features[col].dropna()
        if (values < 0).any():
            issues.append(f"negative values in {col}")

    # Leakage sanity: no future equipment values (as-of join check).
    # fleet_availability must never exceed 1.0 (ratio) — catches join errors.
    if (features["fleet_availability"].dropna() > 1.0).any():
        issues.append("fleet_availability exceeds 1.0 (join error suspected)")

    # Target coverage: zones with zero actual_production rows.
    zero_actual = features[features["actual_production"] == 0]
    if len(zero_actual) > len(features) * 0.2:
        issues.append(f"{len(zero_actual)} rows with actual_production == 0 (>20%)")

    # Missingness flags vs values consistency.
    for flag, col in (
        ("has_weather", "rainfall_1d"),
        ("has_equipment", "fleet_availability"),
        ("has_blast_same_day", "blast_delay_same_day"),
    ):
        inconsistent = (features[flag] != features[col].notna()).sum()
        if inconsistent:
            issues.append(f"{inconsistent} rows where {flag} disagrees with {col}")

    return {
        "table": "production_features",
        "rows": len(features),
        "columns": len(features.columns),
        "missing_pct": missing,
        "issues": issues,
        "ok": not issues,
    }


def summary_report(reserve_report: dict, production_report: dict) -> dict:
    """Combined pipeline quality summary (saved to ml/data/processed/)."""
    return {
        "reserve": reserve_report,
        "production": production_report,
        "overall_ok": reserve_report["ok"] and production_report["ok"],
    }
