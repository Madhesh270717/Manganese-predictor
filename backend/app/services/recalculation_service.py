"""Recalculation loop orchestrator — Phase 21 (PRD Section 24).

Implements the exact loop:

    CURRENT DATA → CURRENT SCHEDULE → PRODUCTION PREDICTION
    → RISK DETECTED? → (no) exit "stable"
    → OPTIMIZER (ranked candidates) → NEW SCHEDULE → RE-PREDICTION
    → IMPROVED? → (yes) recommend | (no) try next candidate (up to 3)
    → none improve → "no improving alternative found"

Duplicate suppression (documented behavior): if a recommendation for the
same equipment is already pending_approval, the cycle UPDATES it when
conditions changed, or SKIPS regeneration when unchanged.

Scope decision (documented): production would use event-driven triggers
(message queue on data ingestion); this prototype uses manual trigger +
lightweight polling of a state file (no durable DB for background state —
documented simplification).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

# In-memory state for the polling mechanism (documented prototype scope).
_POLLING_STATE = {
    "active": False,
    "last_ran_at": None,
    "last_trigger_reason": None,
}
_POLLING_LOCK = threading.Lock()

# Pending recommendations (equipment_id → latest recommendation).
_PENDING_RECOMMENDATIONS: dict[str, dict] = {}

MAX_CANDIDATE_ATTEMPTS = 3

HISTORY_FILE = Path(__file__).resolve().parents[3] / "ml" / "data" / "processed" / "recalculation_history.jsonl"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _current_schedule() -> list[dict]:
    from app.services.production_prediction_service import _current_schedule

    return _current_schedule()


def _current_shortfall() -> float:
    from app.services.shortfall_service import get_current_shortfall

    return get_current_shortfall()["shortfall_tonnes"]


def _risk_reason() -> str | None:
    from ml.pipelines.optimization.risk_trigger import detect_schedule_risks

    triggers = detect_schedule_risks(_current_schedule())
    if not triggers:
        return None
    top = triggers[0]
    return f"{top['equipment_id']}@{top['current_zone_id']}: {top['risk_reason']}"


def _record_log(entry: dict) -> None:
    """Append to the recalculation history (JSONL file, no DB dependency)."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    with _POLLING_LOCK:
        _POLLING_STATE["last_ran_at"] = entry["triggered_at"]
        _POLLING_STATE["last_trigger_reason"] = entry["trigger_reason"]


def _shortfall_for_candidate(equipment_id: str, to_zone: str) -> float:
    from app.services.shortfall_service import get_scenario_shortfall

    schedule = _current_schedule()
    scenario = [dict(e) for e in schedule]
    for entry in scenario:
        if entry["equipment_id"] == equipment_id:
            entry["zone_id"] = to_zone
    return get_scenario_shortfall(scenario)["shortfall_tonnes"]


def run_recalculation_cycle() -> dict:
    """One full PRD §24 cycle. Returns the outcome payload."""
    from ml.pipelines.optimization.candidate_zones import select_candidate_zones
    from ml.pipelines.optimization.zone_comparator import rank_candidates
    from ml.pipelines.optimization.risk_trigger import detect_schedule_risks
    from app.services.recommendation_service import generate_recommendation

    triggered_at = _now().isoformat()
    schedule = _current_schedule()

    # Risk detection: exit cleanly if stable.
    triggers = detect_schedule_risks(schedule)
    if not triggers:
        entry = {
            "triggered_at": triggered_at,
            "trigger_reason": "schedule stable",
            "previous_shortfall": _current_shortfall(),
            "new_shortfall": _current_shortfall(),
            "recommendation_id": None,
            "outcome": "stable",
            "detail": "no risk detected",
        }
        _record_log(entry)
        return {"outcome": "stable", "log": entry}

    # Optimizer: evaluate candidates for the top-risk equipment.
    # Try up to MAX_CANDIDATE_ATTEMPTS candidates — genuine branching.
    top_trigger = triggers[0]
    equipment_id = top_trigger["equipment_id"]
    from_zone = top_trigger["current_zone_id"]
    candidates = select_candidate_zones(equipment_id, from_zone)
    if not candidates:
        entry = {
            "triggered_at": triggered_at,
            "trigger_reason": _risk_reason() or "risk",
            "previous_shortfall": _current_shortfall(),
            "new_shortfall": _current_shortfall(),
            "recommendation_id": None,
            "outcome": "no_improvement",
            "detail": "no candidate zones",
        }
        _record_log(entry)
        return {"outcome": "no_improvement", "log": entry}

    ranked = rank_candidates(equipment_id, candidates, schedule)
    baseline_shortfall = _current_shortfall()

    for candidate in ranked[:MAX_CANDIDATE_ATTEMPTS]:
        to_zone = candidate["candidate_zone_id"]
        new_shortfall = _shortfall_for_candidate(equipment_id, to_zone)

        if new_shortfall < baseline_shortfall:
            # Improvement: package the recommendation (Phase 20), with
            # duplicate suppression against pending recommendations.
            recommendation = generate_recommendation(equipment_id)
            if recommendation is None:
                recommendation = {
                    "equipment_id": equipment_id,
                    "to_zone": to_zone,
                    "expected_impact": {},
                }

            existing = _PENDING_RECOMMENDATIONS.get(equipment_id)
            if existing is not None:
                # Same recommendation already pending — skip regeneration.
                entry = {
                    "triggered_at": triggered_at,
                    "trigger_reason": _risk_reason() or "risk",
                    "previous_shortfall": baseline_shortfall,
                    "new_shortfall": new_shortfall,
                    "recommendation_id": f"{equipment_id}->{to_zone}",
                    "outcome": "recommended",
                    "detail": "existing pending recommendation unchanged — skipped",
                }
                _record_log(entry)
                return {"outcome": "recommended", "skipped_duplicate": True, "log": entry}

            _PENDING_RECOMMENDATIONS[equipment_id] = recommendation
            entry = {
                "triggered_at": triggered_at,
                "trigger_reason": _risk_reason() or "risk",
                "previous_shortfall": baseline_shortfall,
                "new_shortfall": new_shortfall,
                "recommendation_id": f"{equipment_id}->{to_zone}",
                "outcome": "recommended",
                "detail": f"moved {equipment_id} {from_zone}->{to_zone}",
            }
            _record_log(entry)
            return {
                "outcome": "recommended",
                "recommendation": recommendation,
                "tried_candidates": 1,
                "log": entry,
            }

    # None of the top candidates improved — report honestly.
    entry = {
        "triggered_at": triggered_at,
        "trigger_reason": _risk_reason() or "risk",
        "previous_shortfall": baseline_shortfall,
        "new_shortfall": baseline_shortfall,
        "recommendation_id": None,
        "outcome": "no_improvement",
        "detail": f"top {MAX_CANDIDATE_ATTEMPTS} candidates did not reduce shortfall",
    }
    _record_log(entry)
    return {
        "outcome": "no_improvement",
        "tried_candidates": MAX_CANDIDATE_ATTEMPTS,
        "log": entry,
    }


def read_history(limit: int = 50) -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    lines = HISTORY_FILE.read_text(encoding="utf-8").strip().splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return entries[-limit:]


def get_polling_status() -> dict:
    with _POLLING_LOCK:
        return dict(_POLLING_STATE)


def start_polling(interval_seconds: int = 60) -> None:
    """Start the background polling thread (prototype mechanism)."""
    with _POLLING_LOCK:
        if _POLLING_STATE["active"]:
            return
        _POLLING_STATE["active"] = True

    def _poll():
        import time

        while True:
            try:
                run_recalculation_cycle()
            except Exception:
                pass
            time.sleep(interval_seconds)

    threading.Thread(target=_poll, daemon=True, name="recalculation-poller").start()


def stop_polling() -> None:
    with _POLLING_LOCK:
        _POLLING_STATE["active"] = False
