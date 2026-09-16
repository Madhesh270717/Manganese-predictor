from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=f"{settings.app_name} API",
    version=settings.version,
    description=(
        "Spotter AI — manganese reserve mapping, production prediction & "
        "dynamic mine scheduling. Consolidated Phase 22 API; full map in "
        "docs/API_REFERENCE.md."
    ),
)

# CORS: allow the local frontend dev servers (Phases 23–28).
aapp.add_middleware(
    CORSMiddleware,
   allow_origins=[
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "https://manganese-predictor-gn9d.vercel.app",
    "https://manganese-predictor.vercel.app",
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


# --- global error handlers (Phase 22) ---

def _error_payload(status: int, detail) -> dict:
    return {
        "success": False,
        "data": None,
        "error": {"code": status, "message": str(detail)},
    }


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content=_error_payload(exc.status_code, exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=_error_payload(422, exc.errors()))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=_error_payload(500, "internal server error"))


@app.get("/health", tags=["health"])
def health() -> dict:
    """Liveness + real DB connectivity check against Supabase.

    Performs an actual `SELECT 1` (plus a PostGIS function check) so the
    response reflects live connectivity, not a static OK.
    """
    db_connected = False
    postgis_available = False
    db_error = None
    try:
        from sqlalchemy import text

        from app.core.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_connected = True
            try:
                row = conn.execute(text("SELECT ST_AsText(ST_Point(0,0))")).scalar_one()
                postgis_available = row == "POINT(0 0)"
            except Exception:
                postgis_available = False
    except Exception as exc:
        db_error = exc.__class__.__name__

    return {
        "status": "ok" if db_connected else "degraded",
        "service": settings.app_name,
        "db_connected": db_connected,
        "postgis_available": postgis_available,
        "db_error": db_error,
    }


@app.get("/health/ready", tags=["health"])
def health_ready() -> dict:
    """Readiness: DB connectivity + trained model artifacts (Phases 12/15)."""
    checks = {}

    try:
        from sqlalchemy import text

        from app.core.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as exc:
        checks["database"] = {"status": "unavailable", "error": exc.__class__.__name__}

    from pathlib import Path

    # main.py is at backend/app/main.py → repo root is parents[2].
    repo_root = Path(__file__).resolve().parents[2]
    artifacts = {
        "reserve_prospectivity_model": repo_root / "ml" / "pipelines" / "reserve_model" / "artifacts" / "reserve_prospectivity_model.joblib",
        "production_prediction_model": repo_root / "ml" / "pipelines" / "production_model" / "artifacts" / "production_prediction_model.joblib",
    }
    for name, path in artifacts.items():
        checks[name] = {"status": "ok" if path.exists() else "missing", "path": str(path)}

    ready = checks["database"]["status"] == "ok" and all(
        c["status"] == "ok" for c in checks.values() if isinstance(c, dict)
    )
    return {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
    }
