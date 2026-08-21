from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.factor_taxonomy_cache import TAXONOMY_CACHE_TTL_SECONDS
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import (
    ModuleTypeEnum,
    get_data_entry_types_for_module_type,
    get_module_type_for_data_entry_type,
)
from app.models.user import User
from app.schemas.data_entry import BaseModuleHandler
from app.schemas.taxonomy import TaxonomyNode
from app.services.module_handler_service import ModuleHandlerService

router = APIRouter()

# Mirrors the server-side cache TTL (#2258): the browser doesn't need to
# re-fetch identical taxonomy data across the ~11 parallel calls one report
# page load fires. `private` because the endpoint sits behind auth. Stacked
# on top of the server TTL, worst-case staleness after an ingestion job is
# ~2x this value (see docs/src/implementation-plans/2258-cache-factors-query.md).
_CACHE_CONTROL = f"private, max-age={int(TAXONOMY_CACHE_TTL_SECONDS)}"


@router.get(
    "/module_type/{module_type}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module_type(
    response: Response,
    module_type: ModuleTypeEnum,
    year: int = Query(
        default_factory=lambda: datetime.now().year,
        description="Year for which to retrieve the taxonomy",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxonomyNode:
    """Get taxonomy for a given module type."""
    # Taxonomies are year-parameterized classification metadata with no unit
    # data; authentication is the only gate — the simulators render every
    # module's form for any unit member.
    response.headers["Cache-Control"] = _CACHE_CONTROL
    handler_service = ModuleHandlerService(db)
    nodes = []
    for data_entry_type in get_data_entry_types_for_module_type(module_type):
        handler = BaseModuleHandler.get_by_type(data_entry_type)
        nodes.append(await handler_service.get_taxonomy(handler, data_entry_type, year))

    return TaxonomyNode(
        name=module_type.name,
        label=BaseModuleHandler.to_label(module_type.name),
        children=nodes,
    )


@router.get(
    "/data_entry_type/{data_entry_type}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_data_entry_type(
    response: Response,
    data_entry_type: DataEntryTypeEnum,
    year: int = Query(
        default_factory=lambda: datetime.now().year,
        description="Year for which to retrieve the taxonomy",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxonomyNode:
    """Get taxonomy for a given data entry type."""
    module_type = get_module_type_for_data_entry_type(data_entry_type)
    if not module_type:
        raise HTTPException(status_code=404, detail="Module type not found")
    # Taxonomies are year-parameterized classification metadata with no unit
    # data; authentication is the only gate — the simulators render every
    # module's form for any unit member.
    response.headers["Cache-Control"] = _CACHE_CONTROL
    handler = BaseModuleHandler.get_by_type(data_entry_type)
    handler_service = ModuleHandlerService(db)
    return await handler_service.get_taxonomy(handler, data_entry_type, year)


@router.get(
    "/module/{module}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module(
    response: Response,
    module: str,
    year: int = Query(
        default_factory=lambda: datetime.now().year,
        description="Year for which to retrieve the taxonomy",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxonomyNode:
    """Get taxonomy for a given module and data entry type."""
    module_name = module.replace("-", "_")
    if module_name not in ModuleTypeEnum.__members__:
        raise HTTPException(status_code=404, detail="Module not found")
    module_type = ModuleTypeEnum[module_name]
    return await get_taxonomy_for_module_type(
        response, module_type, year, db, current_user
    )


@router.get(
    "/module/{module}/{data_entry}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module_data_entry(
    response: Response,
    module: str,
    data_entry: str,
    year: int = Query(
        default_factory=lambda: datetime.now().year,
        description="Year for which to retrieve the taxonomy",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxonomyNode:
    """Get taxonomy for a given module and data entry type."""
    data_entry_name = data_entry.replace("-", "_")
    data_entry_type = (
        DataEntryTypeEnum[data_entry_name]
        if data_entry_name in DataEntryTypeEnum.__members__
        else None
    )
    if not data_entry_type:
        raise HTTPException(status_code=404, detail="Data entry type not found")
    module_type = get_module_type_for_data_entry_type(data_entry_type)
    if not module_type:
        raise HTTPException(status_code=404, detail="Module type not found")
    if module_type.name != module.replace("-", "_"):
        raise HTTPException(
            status_code=400,
            detail=f"Data entry type {data_entry} does not belong to module {module}",
        )
    return await get_taxonomy_for_data_entry_type(
        response, data_entry_type, year, db, current_user
    )
