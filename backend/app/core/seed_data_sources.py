"""Data Source Registry — PRD Section 39 (real vs synthetic + confidence).

Upserts the eight dataset categories into DATA_SOURCE_METADATA. Sources
reference PRD Section 38 (GSI, NGDR, BhuKosh, ISRO/Bhuvan/Sentinel/Landsat,
IMD/NASA GPM, MOIL, synthetic-generated).

Usage:
    python -m app.core.seed_data_sources
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.models import DataSourceMetadata

DATA_SOURCE_REGISTRY: list[dict] = [
    {
        "dataset_name": "Geological",
        "source_type": "synthetic",
        "confidence_level": "SYNTHETIC",
        "source_name": "synthetic-generated (GSI/BhuKosh inaccessible: login-gated)",
    },
    {
        "dataset_name": "Satellite",
        "source_type": "real",
        "confidence_level": "HIGH",
        "source_name": "ISRO/Bhuvan, Sentinel, Landsat",
    },
    {
        "dataset_name": "Weather",
        "source_type": "real",
        "confidence_level": "HIGH",
        "source_name": "IMD, NASA GPM",
    },
    {
        "dataset_name": "Production",
        "source_type": "synthetic",
        "confidence_level": "MEDIUM",
        "source_name": "synthetic-generated (MOIL zone-level data unavailable)",
    },
    {
        "dataset_name": "Equipment",
        "source_type": "synthetic",
        "confidence_level": "SYNTHETIC",
        "source_name": "synthetic-generated",
    },
    {
        "dataset_name": "Blasting",
        "source_type": "synthetic",
        "confidence_level": "SYNTHETIC",
        "source_name": "synthetic-generated",
    },
    {
        "dataset_name": "Geochemical",
        "source_type": "synthetic",
        "confidence_level": "SYNTHETIC",
        "source_name": "synthetic-generated (GSI/NGDR inaccessible: login-gated)",
    },
    {
        "dataset_name": "Exploration/Drilling",
        "source_type": "synthetic",
        "confidence_level": "MEDIUM",
        "source_name": "synthetic-generated (GSI/NGDR inaccessible: login-gated)",
    },
    {
        "dataset_name": "MiningSchedule",
        "source_type": "synthetic",
        "confidence_level": "SYNTHETIC",
        "source_name": "synthetic-generated (operational/internal data)",
    },
]


def build_seed_statement(now: datetime):
    """Build the parameterized upsert statement (PostgreSQL dialect)."""
    stmt = insert(DataSourceMetadata).values(
        [{**row, "last_updated": now} for row in DATA_SOURCE_REGISTRY]
    )
    return stmt.on_conflict_do_update(
        index_elements=[DataSourceMetadata.dataset_name],
        set_={
            "source_type": stmt.excluded.source_type,
            "confidence_level": stmt.excluded.confidence_level,
            "source_name": stmt.excluded.source_name,
            "last_updated": stmt.excluded.last_updated,
            "updated_at": now,
        },
    )


def seed_data_sources(session: Session, now: datetime | None = None) -> int:
    """Upsert the registry. Returns the number of rows inserted or updated."""
    if now is None:
        now = datetime.now(timezone.utc)

    result = session.execute(build_seed_statement(now))
    session.commit()
    return result.rowcount


def get_registry(session: Session) -> list[DataSourceMetadata]:
    """Read back the full registry, ordered by dataset name."""
    return list(session.scalars(select(DataSourceMetadata).order_by(DataSourceMetadata.dataset_name)))


if __name__ == "__main__":
    with SessionLocal() as session:
        count = seed_data_sources(session)
        print(f"Seeded DATA_SOURCE_METADATA: {count} rows upserted.")
