from fastapi import APIRouter

# Phase 22: consolidated router — every endpoint from Phases 3–21, versioned
# under /api/v1, grouped by module. The Phase 1 placeholder ping routers
# (reserve/production/optimization/assistant/mineability) were removed —
# their module functionality is served by the real routers below.
from app.api import (
    assistant,
    data_confidence,
    demo,
    equipment,
    explainability,
    features,
    metrics,
    mineability_score,
    optimization_alternatives,
    optimization_validate,
    production_prediction,
    production_schedule,
    recalculation,
    recommendations,
    reserve_model,
    resource_estimation,
    shortfall,
    weather,
    zones,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(assistant.router)
api_router.include_router(data_confidence.router)
api_router.include_router(demo.router)
api_router.include_router(zones.router)
api_router.include_router(weather.router)
api_router.include_router(equipment.router)
api_router.include_router(production_schedule.router)
api_router.include_router(production_prediction.router)
api_router.include_router(shortfall.router)
api_router.include_router(explainability.router)
api_router.include_router(optimization_validate.router)
api_router.include_router(optimization_alternatives.router)
api_router.include_router(recommendations.router)
api_router.include_router(recalculation.router)
api_router.include_router(features.router)
api_router.include_router(metrics.router)
api_router.include_router(reserve_model.router)
api_router.include_router(resource_estimation.router)
api_router.include_router(mineability_score.router)
