"""Sync SQLAlchemy session factory — connects to Supabase PostgreSQL.

DATABASE_URL comes from backend/.env (see .env.example). The engine is
created at import time; a missing DATABASE_URL raises a clear error
(backend/app/core/config.py has no localhost default — no local Postgres
assumption). Tests set a dummy DATABASE_URL via tests/conftest.py.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

_settings = get_settings()

if not _settings.database_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
        "and fill in your Supabase connection string (postgresql://...)."
    )

_url = _settings.database_url
# Supabase's dashboard gives postgres:// or postgresql:// URIs. Normalize
# to a SQLAlchemy driver dialect: psycopg v3 (installed) by default; if the
# user supplies postgresql+psycopg2:// (psycopg2-binary on Python <=3.12)
# that is respected as-is.
_dialect, _, _rest = _url.partition("://")
if "+" not in _dialect:
    _url = "postgresql+psycopg://" + _rest

engine = create_engine(
    _url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5, "sslmode": "require"},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
