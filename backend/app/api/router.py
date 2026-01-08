"""API router configuration."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    backoffice,
    files,
    headcounts,
    inventory,
    modules,
    power_factors,
    resources,
    unit_results,
    units,
    users,
)

api_router = APIRouter()

# Include routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(resources.router, prefix="/resources", tags=["resources"])
api_router.include_router(unit_results.router, prefix="/unit", tags=["unit-results"])
api_router.include_router(backoffice.router, prefix="/backoffice", tags=["backoffice"])
api_router.include_router(modules.router, prefix="/modules", tags=["modules"])
api_router.include_router(units.router, prefix="/units", tags=["units"])
api_router.include_router(
    power_factors.router, prefix="/power-factors", tags=["power-factors"]
)
api_router.include_router(headcounts.router, prefix="/headcounts", tags=["headcounts"])
api_router.include_router(inventory.router, prefix="/inventories", tags=["inventories"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
