"""API security — Phase 22 (PRD Section 41).

API-key authentication for mutating endpoints. Scope decision (documented
in docs/API_REFERENCE.md): read-only GET endpoints stay open for the demo;
POST endpoints (schedule scenarios, recalculation triggers, future
recommendation approvals) require the X-API-Key header. A production
system would use OAuth2/JWT with the PRD §4 roles (Mine Planning Engineer,
Operations Manager, Geologist, Equipment Manager).

Demo key: `spotter-demo` (env-configurable via SPOTTER_API_KEY).
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.core.config import settings

DEMO_API_KEY = "spotter-demo"


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Dependency: reject requests missing/wrong API key (401)."""
    expected = DEMO_API_KEY
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Send X-API-Key header.",
        )
