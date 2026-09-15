"""Success metrics API — Phase 30 (PRD Section 45)."""

from fastapi import APIRouter

from app.services.metrics_service import get_metrics_summary

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary")
def metrics_summary() -> dict:
    """System success metrics aggregated from the Phase 12/13/15/16 reports."""
    return get_metrics_summary()
