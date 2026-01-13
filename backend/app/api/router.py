"""API router configuration."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    backoffice,
    # factors,
    # headcounts,
    # inventory,
    # modules,
    # power_factors,
    # unit_results,
    # units,
    users,
)
from app.api.v2 import carbon_reports, data_entries, units

api_router = APIRouter()

# Include v1 routers (deprecated, will be removed in future)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
# api_router.include_router(unit_results.router, prefix="/unit", tags=["unit-results"])
api_router.include_router(backoffice.router, prefix="/backoffice", tags=["backoffice"])
# api_router.include_router(modules.router, prefix="/modules", tags=["modules"])
# api_router.include_router(units.router, prefix="/units", tags=["units"])
# api_router.include_router(factors.router, prefix="/factors", tags=["factors"])
# api_router.include_router(
#     power_factors.router, prefix="/power-factors", tags=["power-factors"]
# )
# api_router.include_router(headcounts.router, prefix="/headcounts", tags=["headcounts"])
# api_router.include_router(inventory.router, prefix="/inventories", tags=["inventories"])

# Include v2 routers (new naming convention)
api_router.include_router(units.router, prefix="/units", tags=["units"])


api_router.include_router(
    carbon_reports.router, prefix="/carbon-reports", tags=["carbon-reports"]
)

# api_router.include_router(
#     carbon_reports.router, prefix="/inventories", tags=["carbon-reports"]
# )
api_router.include_router(
    data_entries.router, prefix="/data-entries", tags=["data-entries"]
)
