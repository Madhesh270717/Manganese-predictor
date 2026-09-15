from fastapi import APIRouter

router = APIRouter(prefix="/mineability")


@router.get("/ping")
def mineability_ping() -> dict:
    """Placeholder endpoint — Mineability Analysis module."""
    return {"module": "mineability", "status": "placeholder"}
