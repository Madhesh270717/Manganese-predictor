"""Shared API dependencies."""

from app.core.database import SessionLocal

# DB availability is probed once per process: after the first failed
# connection attempt, get_db yields a session that raises on first query
# so endpoint fallbacks trigger without paying the connect timeout per
# request (DB-less demo machines).
_DB_UNAVAILABLE = False
_PROBED = False


def _probe_database() -> bool:
    """Probe connectivity once; cache the result for the process lifetime.

    SessionLocal() is lazy (connects on first query), so a real probe is
    needed to fast-fail DB-less machines instead of stalling each request
    for the full connect timeout.
    """
    global _DB_UNAVAILABLE, _PROBED
    if _PROBED:
        return not _DB_UNAVAILABLE
    _PROBED = True
    try:
        from sqlalchemy import text

        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:
        _DB_UNAVAILABLE = True
        return False


class _DeadSession:
    """Session stand-in that raises immediately on any query.

    Endpoints wrap their DB access in try/except for the synthetic
    fallback; this makes the fallback trigger instantly when the DB is
    known to be down.
    """

    def scalar(self, *args, **kwargs):
        raise RuntimeError("database unavailable")

    def scalars(self, *args, **kwargs):
        raise RuntimeError("database unavailable")

    def execute(self, *args, **kwargs):
        raise RuntimeError("database unavailable")

    def close(self):
        pass


def get_db():
    if not _probe_database():
        yield _DeadSession()
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
