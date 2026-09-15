from fastapi import APIRouter

router = APIRouter(prefix="/reserve")


@router.get("/ping")
def reserve_ping() -> dict:
    """Placeholder endpoint — Reserve Intelligence module."""
    return {"module": "reserve", "status": "placeholder"}
