"""Pytest configuration — Spotter AI backend.

Sets a dummy DATABASE_URL before any app import so the suite can run on
DB-less machines (endpoints exercise their synthetic fallbacks). A real
Supabase URL in backend/.env is used when present.
"""

import os

# Only set if not already provided (backend/.env takes precedence via
# pydantic-settings, but this guarantees import never fails in CI/tests).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://spotter:spotter@localhost:5432/spotter_ai",
)
