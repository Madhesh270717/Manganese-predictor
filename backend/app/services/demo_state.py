"""Demo state — Phase 30 (PRD Section 44 repeatable demo).

A small, DB-independent state file that records which recommendation was
"accepted" during a demo run, so Screen 6 can show the before/after impact
of an accepted move and the demo can be reset to the pre-accept state
without re-seeding the database.

Prototype scope (documented): in production the accepted recommendation
would be written into the schedule via the Phase 18 schedule-state layer;
here a lightweight JSON file stands in for that transition, consistent
with the Phase 21 recalculation loop's file-based state.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

DEMO_STATE_PATH = (
    Path(__file__).resolve().parents[3]
    / "ml"
    / "data"
    / "processed"
    / "demo_state.json"
)

_LOCK = threading.Lock()


def _read() -> dict:
    if not DEMO_STATE_PATH.exists():
        return {}
    try:
        return json.loads(DEMO_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write(state: dict) -> None:
    DEMO_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEMO_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)


def _state_view(state: dict) -> dict:
    return {
        "accepted": state.get("accepted"),
        "accepted_at": state.get("accepted_at"),
        "reset_at": state.get("reset_at"),
    }


def get_demo_state() -> dict:
    """Current demo state: accepted recommendation (or none)."""
    with _LOCK:
        return _state_view(_read())


def accept_recommendation(recommendation: dict) -> dict:
    """Record an accepted recommendation (Screen 6 'Accept' button).

    Stores the recommendation's from/to zones and its real expected-impact
    figures so the demo narrative (shortfall 7,400t -> 700t) can be shown
    against the ACTUAL computed numbers.
    """
    with _LOCK:
        state = _read()
        state["accepted"] = {
            "equipment_id": recommendation.get("equipment_id"),
            "from_zone": recommendation.get("from_zone"),
            "to_zone": recommendation.get("to_zone"),
            "reason": recommendation.get("reason"),
            "expected_impact": recommendation.get("expected_impact", {}),
            "status": "approved",
        }
        state["accepted_at"] = datetime.now(timezone.utc).isoformat()
        state.pop("reset_at", None)
        _write(state)
        return _state_view(state)


def reset_demo() -> dict:
    """Reset to the pre-demo state (clears any accepted recommendation)."""
    with _LOCK:
        state = _read()
        had_accepted = bool(state.get("accepted"))
        state["accepted"] = None
        state["accepted_at"] = None
        state["reset_at"] = datetime.now(timezone.utc).isoformat()
        _write(state)
        return {"reset": True, "had_accepted": had_accepted, **_state_view(state)}
