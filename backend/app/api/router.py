"""API router configuration."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    backoffice,
    carbon_report,
    carbon_report_module,
    carbon_report_module_stats,
    data_sync,
    factors,
    files,
    locations,
    unit_results,
    units,
    users,
)

api_router = APIRouter()

# Include routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(unit_results.router, prefix="/unit", tags=["unit-results"])
api_router.include_router(backoffice.router, prefix="/backoffice", tags=["backoffice"])
# TODO: rename /modules in the frontend!
api_router.include_router(
    carbon_report_module.router, prefix="/modules", tags=["modules"]
)
# TODO: rename /modules-stats in the frontend!
api_router.include_router(
    carbon_report_module_stats.router, prefix="/modules-stats", tags=["modules-stats"]
)
api_router.include_router(units.router, prefix="/units", tags=["units"])
api_router.include_router(factors.router, prefix="/factors", tags=["factors"])
api_router.include_router(
    carbon_report.router, prefix="/carbon-reports", tags=["carbon-reports"]
)
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(data_sync.router, prefix="/sync", tags=["data-sync"])
