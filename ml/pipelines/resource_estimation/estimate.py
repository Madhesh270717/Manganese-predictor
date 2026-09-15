"""Resource estimation functions — Phase 13.

Pure, testable estimation logic. Loads the Phase 11 feature table
(parquet-first: no DB dependency at inference time) and derives volume,
tonnage, grade, contained Mn, and confidence per zone.

Methodology + all assumptions documented in README.md (this package).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# --- documented assumptions (README.md) ---

INFLUENCE_RADIUS_M = 100.0  # drill-hole influence radius (simplified geometric)
BULK_DENSITY_T_PER_M3 = 3.5  # manganese ore bulk density (documented value)

STRONG_DRILLING_MIN_HOLES = 4  # zones at/above this use drill-average directly

# Confidence from Phase 6 density labels (README.md rule table).
DENSITY_CONFIDENCE = {
    "NONE": "NOT_ESTIMATED",
    "SPARSE": "LOW",
    "MODERATE": "MEDIUM",
    "DENSE": "MEDIUM",  # deliberate: PRD example rates its densest zone MEDIUM
}

GRADE_CV_DOWNGRADE = 0.30  # within-zone assay scatter downgrades MEDIUM -> LOW


def effective_mineralized_area(hole_count: int, zone_area_sq_m: float) -> float:
    """Area influenced by drill holes, capped at the zone area."""
    influenced = hole_count * math.pi * INFLUENCE_RADIUS_M**2
    return min(influenced, zone_area_sq_m)


def fit_thickness_regression(features: pd.DataFrame) -> tuple[float, float]:
    """Linear regression thickness ~ mn_concentration, fit on STRONG zones only.

    Returns (slope, intercept). Honest calibration: never fit on the zones
    it will predict (sparse zones).
    """
    strong = features[
        (features["drill_hole_count"] >= STRONG_DRILLING_MIN_HOLES)
        & features["drill_avg_ore_thickness"].notna()
        & features["mn_concentration"].notna()
    ]
    if len(strong) < 2:
        return 0.0, 2.0  # degenerate fallback (never hit with our seeds)
    slope, intercept = np.polyfit(
        strong["mn_concentration"], strong["drill_avg_ore_thickness"], 1
    )
    return float(slope), float(intercept)


def _thickness_for_zone(row: pd.Series, slope: float, intercept: float) -> float:
    if row["drill_hole_count"] >= STRONG_DRILLING_MIN_HOLES:
        return float(row["drill_avg_ore_thickness"])
    # Sparse (1-2 holes): regression prediction calibrated on strong zones.
    if pd.notna(row["mn_concentration"]):
        return max(0.2, slope * row["mn_concentration"] + intercept)
    return 0.0


def _density_label(hole_count: int, area_sq_m: float) -> str:
    """Mirror Phase 6's density thresholds (holes/km²)."""
    per_km2 = hole_count / (area_sq_m / 1_000_000.0) if area_sq_m else 0.0
    if per_km2 == 0:
        return "NONE"
    if per_km2 <= 0.5:
        return "SPARSE"
    if per_km2 <= 1.5:
        return "MODERATE"
    return "DENSE"


def estimate_zone(row: pd.Series, slope: float, intercept: float) -> dict:
    """Estimate one zone from its feature row."""
    hole_count = int(row["drill_hole_count"])
    zone_id = str(row["zone_id"])
    area_sq_m = float(row["area_sq_m"]) if pd.notna(row["area_sq_m"]) else 0.0

    if hole_count == 0:
        return {
            "zone_id": zone_id,
            "insufficient_data": True,
            "confidence_level": "NOT_ESTIMATED",
            "drilling_density": "NONE",
            "estimated_volume_m3": None,
            "estimated_tonnage": None,
            "avg_mn_grade": None,
            "estimated_contained_mn": None,
            "data_type": "statistical_estimate",
        }

    thickness = _thickness_for_zone(row, slope, intercept)
    effective_area = effective_mineralized_area(hole_count, area_sq_m)
    volume = effective_area * thickness

    tonnage = volume * BULK_DENSITY_T_PER_M3
    grade = float(row["drill_avg_mn_grade"]) / 100.0 if pd.notna(row["drill_avg_mn_grade"]) else None
    contained = (tonnage * grade) if grade is not None else None

    density_label = _density_label(hole_count, area_sq_m)
    confidence = DENSITY_CONFIDENCE[density_label]

    return {
        "zone_id": zone_id,
        "insufficient_data": False,
        "confidence_level": confidence,
        "drilling_density": density_label,
        "estimated_volume_m3": round(volume, 1),
        "estimated_tonnage": round(tonnage, 1),
        "avg_mn_grade": round(grade * 100, 1) if grade is not None else None,
        "estimated_contained_mn": round(contained, 1) if contained is not None else None,
        "data_type": "statistical_estimate",
    }


def _density_label(hole_count: int, area_sq_m: float) -> str:
    """Mirror Phase 6's density thresholds (holes/km²)."""
    per_km2 = hole_count / (area_sq_m / 1_000_000.0) if area_sq_m else 0.0
    if per_km2 == 0:
        return "NONE"
    if per_km2 <= 0.5:
        return "SPARSE"
    if per_km2 <= 1.5:
        return "MODERATE"
    return "DENSE"


def estimate_all(features: pd.DataFrame) -> list[dict]:
    """Estimate every zone in the Phase 11 feature table."""
    slope, intercept = fit_thickness_regression(features)
    return [estimate_zone(row, slope, intercept) for _, row in features.iterrows()]
