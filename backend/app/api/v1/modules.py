"""Unit Results API endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter()


# TODO: use snake_case keys in the response
module_data: Dict[str, Any] = {
    "module_type": "equipment-electric-consumption",
    "unit": "kWh",
    "year": "2025",
    "retrieved_at": "2025-11-30T00:00:00Z",
    "submodules": {
        "sub_scientific": {
            "id": "sub_scientific",
            "name": "Scientific Equipment",
            "count": 4,
            "items": [
                {
                    "name": "Agitator A",
                    "class": "agitator",
                    "sub_class": "large",
                    "act_usage": 70,
                    "pas_usage": 30,
                    "act_power": 500,
                    "pas_power": 50,
                    "kg_co2eq": 120.5,
                },
                {
                    "name": "Centrifuge X",
                    "class": "centrifuge",
                    "sub_class": "bench",
                    "act_usage": 40,
                    "pas_usage": 60,
                    "act_power": 800,
                    "pas_power": 20,
                    "kg_co2eq": 230.2,
                },
                {
                    "name": "Spectrometer S",
                    "class": "spectrometer",
                    "sub_class": "analytical",
                    "act_usage": 25,
                    "pas_usage": 75,
                    "act_power": 300,
                    "pas_power": 10,
                    "kg_co2eq": 45.8,
                },
            ],
            "summary": {
                "total_items": 2,
                "annual_consumption_kwh": 9625,
                "total_kg_co2eq": 396.5,
            },
        },
        "sub_it": {
            "id": "sub_it",
            "name": "IT Equipment",
            "count": 2,
            "items": [
                {
                    "name": "Server Rack 01",
                    "class": "server",
                    "sub_class": "rack",
                    "act_usage": 90,
                    "pas_usage": 10,
                    "act_power": 1200,
                    "pas_power": 200,
                    "kg_co2eq": 850.0,
                },
                {
                    "name": "Workstation 12",
                    "class": "pc",
                    "sub_class": "workstation",
                    "act_usage": 50,
                    "pas_usage": 50,
                    "act_power": 250,
                    "pas_power": 10,
                    "kg_co2eq": 95.4,
                },
            ],
            "summary": {
                "total_items": 2,
                "annual_consumption_kwh": 14500,
                "total_kg_co2eq": 945.4,
            },
        },
        "sub_other": {
            "id": "sub_other",
            "name": "Other",
            "count": 2,
            "items": [
                {
                    "name": "Incubator I",
                    "class": "incubator",
                    "sub_class": "cell-culture",
                    "act_usage": 60,
                    "pas_usage": 40,
                    "act_power": 600,
                    "pas_power": 100,
                    "kg_co2eq": 310.1,
                },
                {
                    "name": "Fume Hood FH-2",
                    "class": "hood",
                    "sub_class": "fume",
                    "act_usage": 30,
                    "pas_usage": 70,
                    "act_power": 1000,
                    "pas_power": 50,
                    "kg_co2eq": 412.7,
                },
            ],
            "summary": {
                "total_items": 2,
                "annual_consumption_kwh": 7800,
                "total_kg_co2eq": 722.8,
            },
        },
    },
    "totals": {
        "total_submodules": 3,
        "total_items": 7,
        "total_annual_consumption_kwh": 31925,
        "total_kg_co2eq": 2064.7,
    },
}


@router.get("/{module_id}/{unit_id}/{year}", response_model=dict)
async def get_module(
    module_id: str,
    unit_id: str,
    year: int,
    preview_limit: int = Query(default=20, le=100),  # first N items per submodule
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # fetch full data
    data = module_data  # your existing fetch logic

    # trim items to preview_limit, add has_more flag
    for sub_id, sub in data["submodules"].items():
        total = len(sub["items"])
        sub["items"] = sub["items"][:preview_limit]
        sub["has_more"] = total > preview_limit
        sub["total_items"] = total

    return data


# separate endpoint for full submodule data (only if user paginates/scrolls)
@router.get("/{module_id}/{unit_id}/{year}/{submodule_id}", response_model=dict)
async def get_submodule(
    module_id: str,
    unit_id: str,
    year: int,
    submodule_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # fetch and paginate single submodule
    sub = module_data["submodules"].get(submodule_id)
    if not sub:
        raise HTTPException(404, "Submodule not found")

    start = (page - 1) * limit
    return {
        **sub,
        "items": sub["items"][start : start + limit],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": len(sub["items"]),
        },
    }
