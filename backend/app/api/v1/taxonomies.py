from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.policy import check_module_permission
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import (
    ModuleTypeEnum,
    get_data_entry_types_for_module_type,
    get_module_type_for_data_entry_type,
)
from app.models.taxonomy import TaxonomyNode
from app.models.user import User
from app.schemas.data_entry import BaseModuleHandler
from app.services.module_handler_service import ModuleHandlerService

router = APIRouter()


@router.get(
    "/module_type/{module_type}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module_type(
    module_type: ModuleTypeEnum,
    year: int = Query(
        default_factory=lambda: datetime.now().year,
        description="Year for which to retrieve the taxonomy",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxonomyNode:
    """Get taxonomy for a given module type."""
    await check_module_permission(current_user, module_type.name, "view")
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
    await check_module_permission(current_user, module_type.name, "view")
    handler = BaseModuleHandler.get_by_type(data_entry_type)
    handler_service = ModuleHandlerService(db)
    return await handler_service.get_taxonomy(handler, data_entry_type, year)


@router.get(
    "/module/{module}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module(
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
    await check_module_permission(current_user, module_type.name, "view")
    return await get_taxonomy_for_module_type(module_type, year, db, current_user)


@router.get(
    "/module/{module}/{data_entry}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module_data_entry(
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
    # data_entry_name = data_entry.replace("-", "_")
    data_entry_type = (
        DataEntryTypeEnum[data_entry]
        if data_entry in DataEntryTypeEnum.__members__
        # DataEntryTypeEnum[data_entry_name]
        # if data_entry_name in DataEntryTypeEnum.__members__
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
        data_entry_type, year, db, current_user
    )
