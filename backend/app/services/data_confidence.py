"""Data Confidence service — PRD Section 39.

Exposes confidence metadata for any dataset category and a dashboard-ready
summary payload for the frontend confidence indicator widget.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataSourceMetadata

CATEGORY_ALIASES: dict[str, str] = {
    "exploration": "Exploration/Drilling",
    "drilling": "Exploration/Drilling",
}


def get_confidence(session: Session, dataset: str) -> dict | None:
    """Fetch confidence metadata for one dataset category (exact or aliased name)."""
    name = CATEGORY_ALIASES.get(dataset.lower(), dataset)
    try:
        row = session.scalar(select(DataSourceMetadata).where(DataSourceMetadata.dataset_name == name))
    except Exception:
        row = None
    if row is None:
        # Synthetic fallback: the Phase 3 seed registry (same payload shape).
        from app.core.seed_data_sources import DATA_SOURCE_REGISTRY

        entry = next((r for r in DATA_SOURCE_REGISTRY if r["dataset_name"] == name), None)
        if entry is None:
            return None
        return {
            "dataset": entry["dataset_name"],
            "source_type": entry["source_type"],
            "confidence_level": entry["confidence_level"],
            "source_name": entry["source_name"],
            "last_updated": None,
            "source": "synthetic-fallback",
        }
    return {
        "dataset": row.dataset_name,
        "source_type": row.source_type.value,
        "confidence_level": row.confidence_level.value,
        "source_name": row.source_name,
        "last_updated": row.last_updated.isoformat(),
    }


def get_data_confidence_summary(session: Session) -> dict:
    """Full dashboard-ready payload matching PRD Section 39's layout.

    Shape:
        {
          "datasets": [ {dataset, source_type, confidence_level, source_name, last_updated}, ... ],
          "summary": { "Geological": "HIGH", ..., }
        }
    """
    try:
        rows = session.scalars(select(DataSourceMetadata).order_by(DataSourceMetadata.dataset_name)).all()
    except Exception:
        rows = None

    if not rows:
        # Synthetic fallback: the Phase 3 seed registry.
        from app.core.seed_data_sources import DATA_SOURCE_REGISTRY

        datasets = [
            {
                "dataset": r["dataset_name"],
                "source_type": r["source_type"],
                "confidence_level": r["confidence_level"],
                "source_name": r["source_name"],
                "last_updated": None,
            }
            for r in sorted(DATA_SOURCE_REGISTRY, key=lambda e: e["dataset_name"])
        ]
        return {
            "datasets": datasets,
            "summary": {d["dataset"]: d["confidence_level"] for d in datasets},
            "source": "synthetic-fallback",
        }

    datasets = [
        {
            "dataset": row.dataset_name,
            "source_type": row.source_type.value,
            "confidence_level": row.confidence_level.value,
            "source_name": row.source_name,
            "last_updated": row.last_updated.isoformat(),
        }
        for row in rows
    ]
    summary = {d["dataset"]: d["confidence_level"] for d in datasets}
    return {"datasets": datasets, "summary": summary}
