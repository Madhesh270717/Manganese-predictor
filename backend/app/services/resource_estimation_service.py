"""Resource Estimation service — Phase 13.

Serves statistical resource estimates (volume/tonnage/grade/contained Mn)
from the Phase 11 feature table. Parquet-first: no DB dependency at
inference time; the feature table is the single source of truth.

Every output is `data_type: "statistical_estimate"` — NOT a certified
reserve/resource (PRD Section 8).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
FEATURES_PATH = REPO_ROOT / "ml" / "data" / "processed" / "reserve_features.parquet"

DATA_TYPE = "statistical_estimate"
DISCLAIMER = "Statistical estimate — NOT a certified reserve/resource (JORC/UNFC) (PRD Section 8)."


@lru_cache(maxsize=1)
def _estimates() -> dict[str, dict]:
    from ml.pipelines.resource_estimation.estimate import estimate_all

    frame = pd.read_parquet(FEATURES_PATH)
    return {e["zone_id"]: e for e in estimate_all(frame)}


def get_resource_estimate(zone_id: str) -> dict | None:
    """Single-zone resource estimate (None if zone unknown)."""
    estimate = _estimates().get(zone_id)
    if estimate is None:
        return None
    return {**estimate, "disclaimer": DISCLAIMER}


def get_all_resource_estimates() -> dict:
    """All-zone payload; insufficient_data zones are included, not omitted."""
    estimates = sorted(_estimates().values(), key=lambda e: e["zone_id"])
    return {
        "count": len(estimates),
        "estimates": [{**e, "disclaimer": DISCLAIMER} for e in estimates],
        "data_type": DATA_TYPE,
        "disclaimer": DISCLAIMER,
    }
