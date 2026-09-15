"""Data confidence API — PRD Section 39 indicator endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.data_confidence import get_confidence, get_data_confidence_summary

router = APIRouter(prefix="/data-confidence", tags=["data-confidence"])


@router.get("")
def data_confidence_summary(db: Session = Depends(get_db)) -> dict:
    """Full data confidence summary for the frontend indicator widget."""
    return get_data_confidence_summary(db)


@router.get("/{dataset}")
def data_confidence_detail(dataset: str, db: Session = Depends(get_db)) -> dict:
    """Confidence metadata for a single dataset category."""
    result = get_confidence(db, dataset)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset category: {dataset}")
    return result
