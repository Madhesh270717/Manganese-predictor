from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend .env lives in backend/ — anchor it to this file so the same
# settings resolve regardless of the process CWD (uvicorn from backend/,
# alembic from database/, seed scripts, tests).
# config.py is at backend/app/core/config.py → parents[2] = backend/
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "spotter-ai-backend"
    version: str = "0.1.0"
    debug: bool = False
    # Supabase PostgreSQL connection URI — read from backend/.env (see
    # .env.example). No default: failing loudly beats silently assuming a
    # local Postgres instance.
    database_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "claude-3-5-sonnet-latest"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
