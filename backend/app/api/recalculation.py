"""Recalculation API — Phase 21 (PRD Section 24)."""

from fastapi import APIRouter, Depends

from app.core.security import require_api_key
from app.services.recalculation_service import (
    get_polling_status,
    read_history,
    run_recalculation_cycle,
    start_polling,
)

router = APIRouter(prefix="/recalculation", tags=["recalculation-loop"])


@router.post("/trigger")
def trigger_recalculation(_: None = Depends(require_api_key)) -> dict:
    """Manually trigger one recalculation cycle (demo/frontend path).

    Requires X-API-Key (mutating action).
    """
    return run_recalculation_cycle()


@router.get("/history")
def recalculation_history(limit: int = 50) -> dict:
    """Recalculation audit log."""
    entries = read_history(limit)
    return {"count": len(entries), "entries": entries}


@router.get("/status")
def recalculation_status() -> dict:
    """Polling state (active, last run, last trigger reason)."""
    return get_polling_status()
