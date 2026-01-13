"""Data Entry API endpoints (modules data)."""

from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.user import User

# from app.schemas.headcount import (
#     HeadCountCreate,
#     HeadCountCreateRequest,
#     HeadcountItemResponse,
#     HeadCountUpdate,
#     HeadCountUpdateRequest,
# )
from app.schemas.data_entry import DataEntryCreate, DataEntryResponse, DataEntryUpdate
from app.schemas.equipment import (
    # EquipmentCreateRequest,
    # EquipmentDetailResponse,
    # EquipmentUpdateRequest,
    ModuleResponse,
    SubmoduleResponse,
)
from app.services.data_entry_service import DataEntryService

# from app.services import equipment_service
# from app.services.headcount_service import HeadcountService

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/{carbon_report_module_id}/stats",
    response_model=dict[str, float],
)
async def get_data_entry_stats(
    carbon_report_module_id: int,
    # data_entry_type_id: str,
    aggregate_by: str = Query(
        default="data_entry_type_id", description="Aggregate by field"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, float]:
    """
    Get data entry statistics such as total items and submodules.

    Args:
        data_entry_type_id: Data entry type identifier (e.g., 'equipment-electric-consumption')
        unit_id: Unit ID to filter data
        year: Year for the data
        db: Database session
        current_user: Authenticated user
    Returns:
        Dict with statistics (e.g., total items, total submodules)
    """
    logger.info(f"carbon_report_module_id={sanitize(carbon_report_module_id)}")

    stats: dict[str, float] = {}
    DataEntryService(db).get_module_stats(
        carbon_report_module_id=carbon_report_module_id,
        aggregate_by=aggregate_by,
    )
    logger.info(f"Data entry stats returned: {stats}")

    return stats


@router.get(
    "/{carbon_report_module_id}/{data_entry_type_id}", response_model=ModuleResponse
)
async def get_data_entry(
    carbon_report_module_id: int,
    data_entry_type_id: str,
    preview_limit: int = Query(
        default=20, ge=0, le=100, description="Items per submodule"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get data entry data with items and emissions.

    Returns data items grouped by submodule with pre-calculated
    emissions from the database. Preview mode returns limited items
    per submodule.

    Args:
        data_entry_type_id: Data entry type identifier
        unit_id: Unit ID to filter data
        year: Year for the data
        preview_limit: Max items per submodule (default 20, max 100)
        db: Database session
        current_user: Authenticated user

    Returns:
        ModuleResponse with submodules, items, and calculated totals
    """
    logger.info(
        f"GET data entry: data_entry_type_id={sanitize(data_entry_type_id)}, "
        f"carbon_report_module_id={sanitize(carbon_report_module_id)}, "
        f"preview_limit={sanitize(preview_limit)}"
    )

    module_data: ModuleResponse = None
    module_data = await DataEntryService(db).get_module_data(
        carbon_report_module_id=carbon_report_module_id,
    )
    stats = await DataEntryService(db).get_module_stats(
        carbon_report_module_id=carbon_report_module_id,
        aggregate_by="function_role",
    )
    module_data.totals.total_items = int(stats.get("total_items", 0))
    module_data.totals.total_submodules = 0
    module_data.stats = stats

    if module_data:
        logger.info(
            f"Data entry data returned: {module_data.totals.total_items} items "
            f"across {module_data.totals.total_submodules} submodules"
        )

    return module_data


@router.get(
    "/{carbon_report_module_id}/{data_entry_type_id}/{submodule_id}",
    response_model=SubmoduleResponse,
)
async def get_data_entry_submodule(
    carbon_report_module_id: int,
    data_entry_type_id: int,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=50, le=100, description="Items per page"),
    sort_by: str = Query(default="id", description="Field to sort by"),
    sort_order: str = Query(default="asc", description="Sort order: 'asc' or 'desc'"),
    filter: Optional[str] = Query(
        default=None, description="Filter string to search in name or display_name"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get paginated data for a single submodule.

    Args:
        data_entry_type_id: Data entry type identifier
        unit_id: Unit ID to filter data
        year: Year for the data
        submodule_id: Submodule ID (e.g., 'sub_scientific')
        page: Page number (1-indexed)
        limit: Items per page (max 100)
        sort_by: Field name to sort by
        sort_order: Sort order ('asc' or 'desc')
        db: Database session
        current_user: Authenticated user

    Returns:
        SubmoduleResponse with paginated items and summary
    """
    logger.info(
        f"GET data entry submodule: data_entry_type_id={sanitize(data_entry_type_id)}, "
        f"carbon_report_module_id={sanitize(carbon_report_module_id)}, "
        f"page={sanitize(page)}, "
        f"limit={sanitize(limit)}, sort_by={sanitize(sort_by)}, "
        f"sort_order={sanitize(sort_order)}"
    )

    offset = (page - 1) * limit

    submodule_data = None
    submodule_data = await DataEntryService(db).get_submodule_data(
        carbon_report_module_id=carbon_report_module_id,
        data_entry_type_id=data_entry_type_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        filter=filter,
    )
    if not submodule_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submodule not found",
        )
    logger.info(
        f"Submodule data returned: {len(submodule_data.items)} items "
        f"(total: {submodule_data.count}, page: {sanitize(page)})"
    )

    return submodule_data


# http://localhost:9000/api/v1/data-entries/3/2025/my-lab/member
# {
#   "display_name": "Pierre",
#   "function": "aefae",
#   "fte": 1,
#   "category": "Uncategorized"
# }
@router.post(
    "/{carbon_report_module_id}/{data_entry_type_id}",
    response_model=DataEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_data_entry_item(
    carbon_report_module_id: int,
    data_entry_type_id: str,
    item_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create new data entry item with schema validation.

    Args:
        carbon_report_module_id: Carbon report module ID
        data_entry_type_id: Data entry type identifier
        item_data: Raw JSON data for the item
        db: Database session
        current_user: Authenticated user

    Returns:
        Created item response
    """

    data_entry_service = DataEntryService(db_session=db)

    item = await data_entry_service.create(
        carbon_report_module_id=carbon_report_module_id,
        data_entry_type_id=data_entry_type_id,
        user=current_user,
        data=item_data,
    )
    if item is None:
        logger.error(
            "Failed to create item",
            extra={
                "data_entry_type_id": sanitize(data_entry_type_id),
                "unit_id": sanitize(unit_id),
                "user_id": sanitize(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create item",
        )
    logger.info(
        f"Created {sanitize(data_entry_type_id)}:{sanitize(item.id)} for {sanitize(unit_id)}"
    )

    return item


@router.get(
    "/{carbon_report_module_id}/{data_entry_type_id}/{item_id}",
    response_model=DataEntryResponse,
)
async def get_data_entry_item(
    carbon_report_module_id: int,
    data_entry_type_id: str,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get data entry item by ID.

    Args:
        carbon_report_module_id: Carbon report module ID
        data_entry_type_id: Data entry type identifier
        item_id: Item ID
        db: Database session
        current_user: Authenticated user

    Returns:
        Item response
    """
    logger.info(
        f"GET data entry item: carbon_report_module_id={sanitize(carbon_report_module_id)}, "
        f"data_entry_type_id={sanitize(data_entry_type_id)}, "
        f"item_id={sanitize(item_id)}"
    )
    item: DataEntryResponse = await DataEntryService(db).get_by_id(
        item_id=item_id,
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data entry item not found",
        )
    item = DataEntryResponse.model_validate(item)
    return item


@router.patch(
    "/{}/{data_entry_type_id}/{submodule_id}/{item_id}",
    response_model=DataEntryResponse,
)
async def update_data_entry_item(
    carbon_report_module_id: int,
    data_entry_type_id: int,
    item_id: int,
    item_data: DataEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update data entry item.

    Args:
        carbon_report_module_id: Carbon report module ID
        data_entry_type_id: Data entry type identifier
        item_id: Item ID to update
        item_data: Data for updating the item
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated item response
    """
    logger.info(
        f"PATCH data entry item: report_id={sanitize(carbon_report_module_id)}, "
        f"data_entry_type_id={sanitize(data_entry_type_id)}, "
        f"item_id={sanitize(item_id)}, user={sanitize(current_user.id)}"
    )
    # updateItem = HeadCountUpdate(
    #             **item_data.model_dump(exclude_unset=True),
    #         )

    item: DataEntryUpdate = await DataEntryService(db).update(
        id=item_id,
        data=item_data,
        user=current_user,
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data entry item not found",
        )
    item = DataEntryResponse.model_validate(item)
    # headcount = await HeadcountService(db).update_headcount(
    #         headcount_id=item_id,
    #         data=updateItem,
    #         current_user=current_user,
    #     )
    logger.info(f"Updated item {sanitize(item_id)}")
    return item


@router.delete(
    "/{unit_id}/{year}/{data_entry_type_id}/{submodule_id}/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_data_entry_item(
    unit_id: int,
    year: int,
    data_entry_type_id: str,
    submodule_id: str,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete data entry item.

    Args:
        unit_id: Unit ID (for route consistency)
        year: Year (informational)
        data_entry_type_id: Data entry type identifier
        item_id: Item ID to delete
        db: Database session
        current_user: Authenticated user

    Returns:
        No content (204)
    """
    logger.info(
        f"DELETE data entry item: unit_id={sanitize(unit_id)}, "
        f"year={sanitize(year)}, data_entry_type_id={sanitize(data_entry_type_id)}, "
        f"item_id={sanitize(item_id)}, user={sanitize(current_user.id)}"
    )
    try:
        if data_entry_type_id == "equipment-electric-consumption":
            await equipment_service.delete_equipment(
                session=db,
                equipment_id=item_id,
                user_id=current_user.id,
            )
        elif data_entry_type_id == "my-lab":
            await HeadcountService(db).delete_headcount(
                headcount_id=item_id,
                current_user=current_user,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not supported for deletion",
            )
    except PermissionError as e:
        logger.warning(
            f"Permission error during deletion of item_id={sanitize(item_id)}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
