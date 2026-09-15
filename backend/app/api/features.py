"""Features API — engineered feature lookup (Phase 11 debugging aid)."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from ml.pipelines.feature_engineering.reserve_features import build_reserve_features

router = APIRouter(prefix="/features", tags=["features"])


@lru_cache(maxsize=1)
def _reserve_feature_frame() -> dict[str, dict]:
    """Build the reserve feature table once per process (DB or synthetic).

    Cached: the table is static between data refreshes; a re-seed requires
    an app restart (documented limitation of this debugging endpoint).
    """
    try:
        from ml.pipelines.feature_engineering.loaders import load_from_db

        data = load_from_db()
        source = "db"
    except Exception:
        from ml.pipelines.feature_engineering.loaders import load_from_synthetic

        data = load_from_synthetic()
        source = "synthetic-fallback"

    frame = build_reserve_features(
        zones=data["zones"],
        geological=data["geological"],
        geochemical=data["geochemical"],
        exploration=data["exploration"],
        satellite=data["satellite"],
    )
    rows = {
        row["zone_id"]: {k: (None if pd_isna(v) else _jsonable(v)) for k, v in row.items()}
        for _, row in frame.iterrows()
    }
    return {"source": source, "rows": rows}


def pd_isna(value) -> bool:
    import pandas as pd

    return pd.isna(value)


def _jsonable(value):
    import numpy as np

    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    return value


@router.get("/reserve/{zone_id}")
def reserve_features_for_zone(zone_id: str, db=Depends(get_db)) -> dict:
    """Engineered feature row for one zone (Phase 12 model input preview)."""
    payload = _reserve_feature_frame()
    row = payload["rows"].get(zone_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Zone not found: {zone_id}")
    return {"zone_id": zone_id, "source": payload["source"], "features": row}
