"""SHAP explainability for the production prediction model — Phase 17.

TreeExplainer on the Phase 15 artifact (RF/XGB/GBM are all tree-based).
explain_prediction() returns ranked SHAP values per raw feature for one
instance.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = REPO_ROOT / "ml" / "pipelines" / "production_model" / "artifacts" / "production_prediction_model.joblib"
META_PATH = MODEL_PATH.parent / "model_metadata.json"


@lru_cache(maxsize=1)
def _explainer():
    import joblib
    import shap

    model = joblib.load(MODEL_PATH)
    meta = json.loads(META_PATH.read_text())
    return shap.TreeExplainer(model), meta


def explain_prediction(features_row: dict) -> list[dict]:
    """Ranked SHAP contributions for one prediction instance.

    Args:
        features_row: raw feature dict matching model_metadata feature_columns.

    Returns:
        [{feature_name, shap_value, contribution_percentage}, ...] sorted by
        absolute contribution desc.
    """
    explainer, meta = _explainer()
    columns = meta["feature_columns"]

    X = pd.DataFrame([features_row])[columns].fillna(-1.0).astype(float)
    shap_values = explainer.shap_values(X)

    values = np.asarray(shap_values)[0]
    total_abs = float(np.abs(values).sum()) or 1.0

    ranked = sorted(
        (
            {
                "feature_name": name,
                "shap_value": round(float(value), 3),
                "contribution_percentage": round(float(abs(value)) / total_abs * 100.0, 1),
            }
            for name, value in zip(columns, values)
        ),
        key=lambda item: abs(item["shap_value"]),
        reverse=True,
    )
    return ranked
