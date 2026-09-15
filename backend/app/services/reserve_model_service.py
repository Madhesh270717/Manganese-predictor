"""Reserve Prospectivity prediction service — Phase 12.

Loads the trained artifact and exposes prospectivity scores with the PRD
classification thresholds. Every output is explicitly
`statistical_prospectivity` (PRD Section 8: never a confirmed reserve).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = REPO_ROOT / "ml" / "pipelines" / "reserve_model" / "artifacts" / "reserve_prospectivity_model.joblib"
META_PATH = MODEL_PATH.parent / "model_metadata.json"
FEATURES_PATH = REPO_ROOT / "ml" / "data" / "processed" / "reserve_features.parquet"

# PRD Sections 6–9 thresholds (documented in reserve_model/README.md).
HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.40

COLOR_MAP = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}

DATA_TYPE = "statistical_prospectivity"


def classify(score: float) -> str:
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def _load_frame() -> pd.DataFrame:
    """Feature table used at training time (must match train.py columns)."""
    return pd.read_parquet(FEATURES_PATH)


@lru_cache(maxsize=1)
def _load_model():
    import joblib

    from ml.pipelines.reserve_model.train import FEATURE_COLUMNS, apply_sigmoid

    artifact = joblib.load(MODEL_PATH)
    meta = json.loads(META_PATH.read_text())
    return artifact["model"], artifact.get("calibration_temperature", 0.5), meta, FEATURE_COLUMNS, apply_sigmoid


@lru_cache(maxsize=1)
def _zone_scores() -> dict[str, float]:
    """All-zone prospectivity scores, cached per process.

    The feature table and model are static between data refreshes; caching
    turns the per-zone API/optimizer loops into dict lookups instead of a
    full model re-evaluation per zone.
    """
    model, temperature, meta, feature_cols, apply_sigmoid = _load_model()
    frame = _load_frame()
    X = frame[feature_cols].fillna(0.0).astype(float).values
    raw = model.predict_proba(X)[:, 1]
    calibrated = apply_sigmoid(raw, temperature)
    return dict(zip(frame["zone_id"], calibrated))


def get_prospectivity(zone_id: str) -> dict | None:
    """Single-zone prospectivity result (None if zone unknown)."""
    scores = _zone_scores()
    score = scores.get(zone_id)
    if score is None:
        return None
    classification = classify(float(score))
    return {
        "zone_id": zone_id,
        "prospectivity_score": round(float(score) * 100, 1),
        "classification": classification,
        "color": COLOR_MAP[classification],
        "model_version": _load_model()[2].get("model_version", "v1"),
        "data_type": DATA_TYPE,
        "disclaimer": "Statistical prospectivity — NOT a confirmed geological reserve (PRD Section 8).",
    }


def get_all_zones_prospectivity() -> dict:
    """All-zone map payload for Phase 25 (sorted by score desc)."""
    zones = sorted(
        (get_prospectivity(zone_id) for zone_id in _zone_scores()),
        key=lambda z: z["prospectivity_score"],
        reverse=True,
    )
    return {
        "count": len(zones),
        "zones": zones,
        "thresholds": {
            "high": f">= {int(HIGH_THRESHOLD * 100)}%",
            "medium": f"{int(MEDIUM_THRESHOLD * 100)}-{int(HIGH_THRESHOLD * 100) - 1}%",
            "low": f"< {int(MEDIUM_THRESHOLD * 100)}%",
        },
        "data_type": DATA_TYPE,
        "disclaimer": "Statistical prospectivity — NOT a confirmed geological reserve (PRD Section 8).",
    }
