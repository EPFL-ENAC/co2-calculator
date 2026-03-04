from fastapi import APIRouter, Depends, HTTPException
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

router = APIRouter()


@router.get(
    "/module_type/{module_type}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module_type(
    module_type: ModuleTypeEnum,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxonomyNode:
    """Get taxonomy for a given module type."""
    await check_module_permission(current_user, module_type.name, "view")
    nodes = []
    for data_entry_type in get_data_entry_types_for_module_type(module_type):
        handler = BaseModuleHandler.get_by_type(data_entry_type)
        nodes.append(await handler.get_taxonomy(data_entry_type, db))

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxonomyNode:
    """Get taxonomy for a given data entry type."""
    module_type = get_module_type_for_data_entry_type(data_entry_type)
    if not module_type:
        raise HTTPException(status_code=404, detail="Module type not found")
    await check_module_permission(current_user, module_type.name, "view")
    handler = BaseModuleHandler.get_by_type(data_entry_type)
    return await handler.get_taxonomy(data_entry_type, db)


@router.get(
    "/module/{module}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module(
    module: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxonomyNode:
    """Get taxonomy for a given module and data entry type."""
    module_name = module.replace("-", "_")
    module_type = ModuleTypeEnum[module_name]
    await check_module_permission(current_user, module_type.name, "view")
    return await get_taxonomy_for_module_type(module_type, db, current_user)


@router.get(
    "/module/{module}/{data_entry}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module_data_entry(
    module: str,
    data_entry: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxonomyNode:
    """Get taxonomy for a given module and data entry type."""
    module_type = get_module_type_for_data_entry_type(DataEntryTypeEnum[data_entry])
    if not module_type:
        raise HTTPException(status_code=404, detail="Module type not found")
    if module_type.name != module.replace("-", "_"):
        raise HTTPException(
            status_code=400,
            detail=f"Data entry type {data_entry} does not belong to module {module}",
        )
    await check_module_permission(current_user, module_type.name, "view")
    data_entry_type = DataEntryTypeEnum[data_entry]
    return await get_taxonomy_for_data_entry_type(data_entry_type, db, current_user)
