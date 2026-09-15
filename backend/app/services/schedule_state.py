"""Mutable active-schedule state — Phase 28 (PRD Section 42).

The single source of truth for the CURRENT active schedule. Every service
that reads "the current schedule" (production prediction, shortfall,
recommendations, recalculation) goes through get_active_schedule().

Accepting a recommendation calls apply_move(), which mutates this state —
so Phase 27's schedule view, Phase 23's overview, and all downstream
predictions reflect the change on their next read. No recommendation is
ever applied without an explicit accept call (PRD §42 hard requirement).

On DB-backed deployments apply_move() also writes the MINING_SCHEDULE
table; the in-memory state remains authoritative for this prototype
(documented scope decision — a production system would persist
schedule state transactionally).
"""

from __future__ import annotations

import threading

_lock = threading.Lock()

# None = never mutated → regenerate from the Phase 10 generator on read.
_active_schedule: list[dict] | None = None


def _generate_default() -> list[dict]:
    from app.services.production_prediction_service import _current_schedule as _gen

    return _gen()


def get_active_schedule() -> list[dict]:
    with _lock:
        if _active_schedule is None:
            return _generate_default()
        return [dict(e) for e in _active_schedule]


def apply_move(equipment_id: str, to_zone: str) -> int:
    """Move a unit to a new zone in the active schedule.

    Mutates the active schedule (lazily materialized from the generator on
    first mutation). Returns the number of entries changed.
    """
    with _lock:
        global _active_schedule
        if _active_schedule is None:
            _active_schedule = _generate_default()
        changed = 0
        for entry in _active_schedule:
            if entry["equipment_id"] == equipment_id:
                entry["zone_id"] = to_zone
                changed += 1

        # Best-effort DB write (documented fallback for DB-less machines).
        try:
            _persist_to_db(equipment_id, to_zone)
        except Exception:
            pass

    return changed


def _persist_to_db(equipment_id: str, to_zone: str) -> None:
    from sqlalchemy import update

    from app.core.database import SessionLocal
    from app.models import MiningSchedule

    with SessionLocal() as session:
        session.execute(
            update(MiningSchedule)
            .where(MiningSchedule.equipment_id == equipment_id)
            .values(zone_id=to_zone)
        )
        session.commit()


def reset_active_schedule() -> None:
    """Reset to the generator default (tests + demo re-runs)."""
    with _lock:
        global _active_schedule
        _active_schedule = None
