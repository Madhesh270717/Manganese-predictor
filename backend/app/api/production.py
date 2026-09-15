from fastapi import APIRouter

router = APIRouter(prefix="/production")


@router.get("/ping")
def production_ping() -> dict:
    """Placeholder endpoint — Production Intelligence module."""
    return {"module": "production", "status": "placeholder"}
