"""Demo state API — Phase 30 (PRD Section 44 repeatable demo).

Lets the frontend accept a recommendation (Screen 6) and reset the demo
to the pre-accept state without re-seeding the database.
"""

from fastapi import APIRouter, Depends

from app.core.security import require_api_key
from app.services.demo_state import accept_recommendation, get_demo_state, reset_demo
from app.services.recommendation_service import generate_recommendation

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/state")
def demo_state() -> dict:
    """Current demo state (accepted recommendation or none)."""
    return get_demo_state()


@router.post("/accept")
def demo_accept(_: None = Depends(require_api_key)) -> dict:
    """Accept the top recommendation (marks it approved in demo state).

    Requires X-API-Key (state-changing).
    """
    from app.services.recommendation_service import generate_all_recommendations

    recs = generate_all_recommendations().get("recommendations", [])
    if not recs:
        return {"error": "no active recommendation to accept"}
    rec = generate_recommendation(recs[0]["equipment_id"])
    if rec is None:
        return {"error": "no active recommendation to accept"}
    return accept_recommendation(rec)


@router.post("/reset")
def demo_reset(_: None = Depends(require_api_key)) -> dict:
    """Reset to the pre-demo state (clears accepted recommendation)."""
    return reset_demo()
