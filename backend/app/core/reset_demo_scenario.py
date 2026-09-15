"""Reset the demo scenario to the pre-demo state — Phase 30.

Restores the repeatable PRD Section 44 demo state:
  1. Clears any accepted recommendation (demo_state.json).
  2. Clears the in-memory pending-recommendation registry (Phase 21).
  3. Re-applies the Phase 8 weather demo trigger on A1 (rainfall spike)
     so the risk trigger is fresh for the next run.

Usage (from backend/):
    python -m app.core.reset_demo_scenario
    python -m app.core.reset_demo_scenario --no-weather   # skip re-trigger
"""

from __future__ import annotations

import argparse


def reset_demo(apply_weather: bool = True) -> dict:
    """Run the full reset; returns a summary dict."""
    from app.core.seed_weather import seed_demo
    from app.core.database import SessionLocal
    from app.services.demo_state import reset_demo as reset_state
    from app.services.recalculation_service import _PENDING_RECOMMENDATIONS

    # 1. Clear accepted recommendation state.
    state_result = reset_state()

    # 2. Clear the in-memory pending recommendation registry.
    _PENDING_RECOMMENDATIONS.clear()

    # 3. Re-apply the demo weather trigger (rainfall spike on A1 today).
    weather_count = 0
    if apply_weather:
        try:
            # Fast-fail probe: skip the DB path entirely when unreachable.
            from sqlalchemy import create_engine, select, text

            from app.core.config import get_settings
            from app.models import Zone

            probe = create_engine(
                get_settings().database_url,
                connect_args={"connect_timeout": 2},
            )
            with probe.connect() as conn:
                conn.execute(text("SELECT 1"))
            probe.dispose()

            with SessionLocal() as session:
                zones = list(session.scalars(select(Zone).order_by(Zone.zone_id)).all())
                weather_count = seed_demo(session, zones)
        except Exception as exc:  # DB unavailable — weather trigger is synthetic anyway
            weather_count = -1
            state_result["weather_warning"] = f"could not seed weather (DB unavailable): {exc.__class__.__name__}"

    return {
        **state_result,
        "pending_recommendations_cleared": True,
        "weather_demo_rows": weather_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset the demo to its pre-run state.")
    parser.add_argument(
        "--no-weather",
        action="store_true",
        help="skip re-applying the A1 rainfall demo trigger",
    )
    args = parser.parse_args()

    result = reset_demo(apply_weather=not args.no_weather)
    print("Demo reset complete:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
