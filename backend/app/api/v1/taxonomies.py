from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.security import get_current_active_user
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum, get_data_entry_types_for_module_type
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
    current_user: User = Depends(get_current_active_user),
) -> TaxonomyNode:
    """Get taxonomy for a given module type."""
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
    current_user: User = Depends(get_current_active_user),
) -> TaxonomyNode:
    """Get taxonomy for a given data entry type."""
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
    current_user: User = Depends(get_current_active_user),
) -> TaxonomyNode:
    """Get taxonomy for a given module and data entry type."""
    module_type = ModuleTypeEnum[module]
    return await get_taxonomy_for_module_type(module_type, db)


@router.get(
    "/module/{module}/{data_entry}",
    response_model=TaxonomyNode,
    response_model_exclude_none=True,
)
async def get_taxonomy_for_module_data_entry(
    module: str,
    data_entry: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TaxonomyNode:
    """Get taxonomy for a given module and data entry type."""
    data_entry_type = DataEntryTypeEnum[data_entry]
    return await get_taxonomy_for_data_entry_type(data_entry_type, db)
