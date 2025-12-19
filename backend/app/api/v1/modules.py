"""Unit Results API endpoints."""

from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.headcount import (
    HeadCountCreate,
    HeadCountCreateRequest,
    HeadcountItemResponse,
    HeadCountUpdate,
    HeadCountUpdateRequest,
)
from app.models.user import User
from app.schemas.equipment import (
    EquipmentCreateRequest,
    EquipmentDetailResponse,
    EquipmentUpdateRequest,
    ModuleResponse,
    SubmoduleResponse,
)
from app.services import equipment_service
from app.services.headcount_service import HeadcountService

logger = get_logger(__name__)
router = APIRouter()


@router.get("/{unit_id}/{year}/{module_id}/stats", response_model=dict[str, int])
async def get_module_stats(
    unit_id: str,
    year: int,
    module_id: str,
    aggregate_by: str = Query(default="submodule", description="Aggregate by field"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, int]:
    """
    Get module statistics such as total items and submodules.

    Args:
        module_id: Module identifier
        unit_id: Unit ID to filter equipment
        year: Year for the data
        db: Database session
        current_user: Authenticated user
    Returns:
        List of integers with statistics (e.g., total items, total submodules)
    """
    logger.info(
        f"GET module stats: module_id={sanitize(module_id)}, "
        f"unit_id={sanitize(unit_id)}, year={sanitize(year)}"
    )

    stats: dict[str, int] = {}
    if module_id == "equipment-electric-consumption":
        stats = await equipment_service.get_module_stats(
            session=db,
            unit_id=unit_id,
            aggregate_by=aggregate_by,
        )
    if module_id == "my-lab":
        stats = await HeadcountService(db).get_module_stats(
            unit_id=unit_id,
            year=year,
            aggregate_by=aggregate_by,
        )
    logger.info(f"Module stats returned: {stats}")

    return stats


@router.get("/{unit_id}/{year}/{module_id}", response_model=ModuleResponse)
async def get_module(
    unit_id: str,
    year: int,
    module_id: str,
    preview_limit: int = Query(
        default=20, ge=0, le=100, description="Items per submodule"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get module data with equipment and emissions.

    Returns equipment items grouped by submodule with pre-calculated
    emissions from the database. Preview mode returns limited items
    per submodule.

    Args:
        module_id: Module identifier
        unit_id: Unit ID to filter equipment
        year: Year for the data
        preview_limit: Max items per submodule (default 20, max 100)
        db: Database session
        current_user: Authenticated user

    Returns:
        ModuleResponse with submodules, items, and calculated totals
    """
    logger.info(
        f"GET module: module_id={sanitize(module_id)}, unit_id={sanitize(unit_id)}, "
        f"year={sanitize(year)}, preview_limit={sanitize(preview_limit)}"
    )

    if module_id == "equipment-electric-consumption":
        # Fetch real data from database
        module_data = await equipment_service.get_module_data(
            session=db,
            unit_id=unit_id,
            year=year,
            preview_limit=preview_limit,
        )
    if module_id == "my-lab":
        # Fetch real data from database
        module_data = await HeadcountService(db).get_module_data(
            unit_id=unit_id,
            year=year,
        )
    logger.info(
        f"Module data returned: {module_data.totals.total_items} items "
        f"across {module_data.totals.total_submodules} submodules"
    )

    return module_data


@router.get(
    "/{unit_id}/{year}/{module_id}/{submodule_id}",
    response_model=SubmoduleResponse,
)
async def get_submodule(
    unit_id: str,
    year: int,
    module_id: str,
    submodule_id: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=50, le=100, description="Items per page"),
    sort_by: str = Query(default="id", description="Field to sort by"),
    sort_order: str = Query(default="asc", description="Sort order: 'asc' or 'desc'"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get paginated data for a single submodule.

    Args:
        module_id: Module identifier
        unit_id: Unit ID to filter equipment
        year: Year for the data
        submodule_id: Submodule ID (e.g., 'sub_scientific')
        page: Page number (1-indexed)
        limit: Items per page (max 100)
        sort_by: Field name to sort by (e.g., 'id', 'name', 'kg_co2eq', 'annual_kwh')
        sort_order: Sort order ('asc' or 'desc'), defaults to 'asc'
        db: Database session
        current_user: Authenticated user

    Returns:
        SubmoduleResponse with paginated items and summary
    """
    logger.info(
        f"GET submodule: module_id={sanitize(module_id)}, "
        f"unit_id={sanitize(unit_id)}, year={sanitize(year)}, "
        f"submodule_id={sanitize(submodule_id)}, page={sanitize(page)}, "
        f"limit={sanitize(limit)}, sort_by={sanitize(sort_by)}, "
        f"sort_order={sanitize(sort_order)}"
    )

    # Calculate offset from page number
    offset = (page - 1) * limit

    # Fetch submodule data from database
    submodule_data = None
    if module_id == "equipment-electric-consumption":
        submodule_data = await equipment_service.get_submodule_data(
            session=db,
            unit_id=unit_id,
            submodule_key=submodule_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    if module_id == "my-lab":
        submodule_data = await HeadcountService(db).get_submodule_data(
            unit_id=unit_id,
            year=year,
            submodule_key=submodule_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
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


@router.post(
    "/{unit_id}/{year}/{module_id}/{submodule_id}",
    response_model=Union[EquipmentDetailResponse, HeadcountItemResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    unit_id: str,
    year: int,
    module_id: str,
    submodule_id: str,
    item_data: Union[EquipmentCreateRequest, HeadCountCreateRequest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create new equipment item.

    Args:
        unit_id: Unit ID for the equipment
        year: Year (informational)
        module_id: Module identifier
        submodule_id: Submodule identifier
        item_data: Equipment creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        EquipmentDetailResponse with created equipment
    """
    logger.info(
        f"POST equipment: unit_id={sanitize(unit_id)}, year={sanitize(year)}, "
        f"module_id={sanitize(module_id)}, user={sanitize(current_user.id)}"
    )
    item: Union[EquipmentDetailResponse, HeadcountItemResponse]
    # Validate unit_id matches the one in request body
    if module_id == "equipment-electric-consumption":
        if not isinstance(item_data, EquipmentCreateRequest):
            raise HTTPException(
                status_code=400,
                detail="Invalid item_data for equipment creation at api/v1/modules",
            )

        item = await equipment_service.create_equipment(
            session=db,
            equipment_data=item_data,
            user_id=current_user.id,
        )
    elif module_id == "my-lab":
        headcount_create = HeadCountCreate(
            **item_data.dict(),
            unit_id=unit_id,
            date="2024-12-31",
            submodule=submodule_id,
            unit_name=str(unit_id),
            cf="unknown",
            cf_name="unknown",
            cf_user_id="unknown",
            status="unknown",
            sciper="unknown",
        )
        headcount = await HeadcountService(db).create_headcount(
            data=headcount_create,
            provider_source="manual",
            user_id=current_user.id,
        )
        if headcount is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to create headcount item",
            )
        item = HeadcountItemResponse.model_validate(headcount)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported module_id: {sanitize(module_id)}",
        )
    if item is None:
        logger.error(
            "Failed to create item in module",
            extra={
                "module_id": sanitize(module_id),
                "unit_id": sanitize(unit_id),
                "user_id": sanitize(current_user.id),
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to create equipment item",
        )
    logger.info(
        f"Created {sanitize(module_id)}:{sanitize(item.id)} for {sanitize(unit_id)}"
    )

    return item


@router.get(
    "/{unit_id}/{year}/{module_id}/{submodule_id}/{item_id}",
    response_model=Union[EquipmentDetailResponse, HeadcountItemResponse],
)
async def get_item(
    unit_id: str,
    year: int,
    module_id: str,
    submodule_id: str,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get equipment item by ID.

    Args:
        unit_id: Unit ID (for route consistency)
        year: Year (informational)
        module_id: Module identifier
        equipment_id: Equipment ID
        db: Database session
        current_user: Authenticated user

    Returns:
        EquipmentDetailResponse
    """
    logger.info(
        f"GET equipment: unit_id={sanitize(unit_id)}, year={sanitize(year)}, "
        f"module_id={sanitize(module_id)}, item_id={sanitize(item_id)}"
    )
    item: Union[EquipmentDetailResponse, HeadcountItemResponse]
    if module_id == "equipment-electric-consumption":
        if not isinstance(item_id, int):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid item_id type for equipment retrieval",
            )
        item = await equipment_service.get_equipment_by_id(
            session=db,
            item_id=item_id,
        )
    elif module_id == "my-lab":
        if not isinstance(item_id, int):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid item_id type for headcount retrieval",
            )
        headcount = await HeadcountService(db).get_by_id(
            item_id=item_id,
        )
        if headcount is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Headcount item not found",
            )
        item = HeadcountItemResponse.model_validate(headcount)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment item not found",
        )
    logger.info(f"Retrieved equipment {sanitize(item_id)}")

    return item


@router.patch(
    "/{unit_id}/{year}/{module_id}/{submodule_id}/{item_id}",
    response_model=Union[EquipmentDetailResponse, HeadcountItemResponse],
)
async def update_equipment(
    unit_id: str,
    year: int,
    module_id: str,
    submodule_id: str,
    item_id: int,
    item_data: Union[EquipmentUpdateRequest, HeadCountUpdateRequest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update equipment item.

    Args:
        unit_id: Unit ID (for route consistency)
        year: Year (informational)
        module_id: Module identifier
        equipment_id: Equipment ID to update
        equipment_data: Equipment update data
        db: Database session
        current_user: Authenticated user

    Returns:
        EquipmentDetailResponse with updated equipment
    """
    logger.info(
        f"PATCH equipment: unit_id={sanitize(unit_id)}, "
        f"year={sanitize(year)}, module_id={sanitize(module_id)}, "
        f"item_id={sanitize(item_id)}, "
        f"user={sanitize(current_user.id)}"
    )
    item: Union[EquipmentDetailResponse, HeadcountItemResponse]
    if module_id == "equipment-electric-consumption":
        if not isinstance(item_data, EquipmentUpdateRequest):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid item_data type for equipment update",
            )
        item = await equipment_service.update_equipment(
            session=db,
            item_id=item_id,
            item_data=item_data,
            user_id=current_user.id,
        )
    elif module_id == "my-lab":
        if not isinstance(item_data, HeadCountUpdateRequest):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid item_data type for equipment update",
            )
        updateItem = HeadCountUpdate(
            **item_data.model_dump(exclude_unset=True),
        )
        headcount = await HeadcountService(db).update_headcount(
            headcount_id=item_id,
            data=updateItem,
            user=current_user,
        )
        if headcount is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Headcount item not found",
            )
        item = HeadcountItemResponse.model_validate(headcount)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="module not supported for update",
        )
    logger.info(f"Updated equipment {sanitize(item_id)}")
    return item


@router.delete(
    "/{unit_id}/{year}/{module_id}/{submodule_id}/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_equipment(
    unit_id: str,
    year: int,
    module_id: str,
    submodule_id: str,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete equipment item.

    Args:
        unit_id: Unit ID (for route consistency)
        year: Year (informational)
        module_id: Module identifier
        equipment_id: Equipment ID to delete
        db: Database session
        current_user: Authenticated user

    Returns:
        No content (204)
    """
    logger.info(
        f"DELETE equipment: unit_id={sanitize(unit_id)}, "
        f"year={sanitize(year)}, module_id={sanitize(module_id)}, "
        f"item_id={sanitize(item_id)}, "
        f"user={sanitize(current_user.id)}"
    )
    if module_id == "equipment-electric-consumption":
        await equipment_service.delete_equipment(
            session=db,
            equipment_id=item_id,
            user_id=current_user.id,
        )
    elif module_id == "my-lab":
        await HeadcountService(db).delete_headcount(
            headcount_id=item_id,
            current_user=current_user,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="module not supported for deletion",
        )

    logger.info(f"Deleted equipment {sanitize(item_id)}")
