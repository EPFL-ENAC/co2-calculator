"""Unit Results API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.equipment import (
    EquipmentCreateRequest,
    EquipmentDetailResponse,
    EquipmentUpdateRequest,
    ModuleResponse,
    SubmoduleResponse,
)
from app.services import equipment_service

logger = get_logger(__name__)
router = APIRouter()


@router.get("/{unit_id}/{year}/{module_id}", response_model=ModuleResponse)
async def get_module(
    unit_id: str,
    year: int,
    module_id: str,
    preview_limit: int = Query(default=20, le=100, description="Items per submodule"),
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
    unit_id = str("C1348")  # Temporary hardcode for demo purposes
    logger.info(
        f"GET module: module_id={module_id}, unit_id={unit_id}, "
        f"year={year}, preview_limit={preview_limit}"
    )

    # Fetch real data from database
    module_data = await equipment_service.get_module_data(
        session=db,
        unit_id=unit_id,
        year=str(year),
        preview_limit=preview_limit,
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
        db: Database session
        current_user: Authenticated user

    Returns:
        SubmoduleResponse with paginated items and summary
    """
    logger.info(
        f"GET submodule: module_id={module_id}, unit_id={unit_id}, "
        f"year={year}, submodule_id={submodule_id}, "
        f"page={page}, limit={limit}"
    )

    # Extract submodule key from ID
    if not submodule_id.startswith("sub_"):
        raise HTTPException(
            status_code=400,
            detail="Invalid submodule_id format. Expected 'sub_<key>'",
        )

    submodule_key = submodule_id.replace("sub_", "")

    # Validate submodule key
    if submodule_key not in ["scientific", "it", "other"]:
        raise HTTPException(
            status_code=404,
            detail=f"Submodule '{submodule_key}' not found",
        )

    # Calculate offset from page number
    offset = (page - 1) * limit

    # Fetch submodule data from database
    submodule_data = await equipment_service.get_submodule_data(
        session=db,
        unit_id=unit_id,
        submodule_key=submodule_key,
        limit=limit,
        offset=offset,
    )

    logger.info(
        f"Submodule data returned: {len(submodule_data.items)} items "
        f"(total: {submodule_data.count}, page: {page})"
    )

    return submodule_data


@router.post(
    "/{unit_id}/{year}/{module_id}/equipment",
    response_model=EquipmentDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_equipment(
    unit_id: str,
    year: int,
    module_id: str,
    equipment_data: EquipmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create new equipment item.

    Args:
        unit_id: Unit ID for the equipment
        year: Year (informational)
        module_id: Module identifier
        equipment_data: Equipment creation data
        db: Database session
        current_user: Authenticated user

    Returns:
        EquipmentDetailResponse with created equipment
    """
    logger.info(
        f"POST equipment: unit_id={unit_id}, year={year}, "
        f"module_id={module_id}, user={current_user.id}"
    )

    # Validate unit_id matches the one in request body
    if equipment_data.unit_id != unit_id:
        raise HTTPException(
            status_code=400,
            detail=f"unit_id in path ({unit_id}) must match "
            f"unit_id in request body ({equipment_data.unit_id})",
        )
    equipment_data.unit_id = "C1348"  # Temporary hardcode for demo purposes

    equipment = await equipment_service.create_equipment(
        session=db,
        equipment_data=equipment_data,
        user_id=current_user.id,
    )

    logger.info(f"Created equipment {equipment.id} for unit {unit_id}")

    return equipment


@router.get(
    "/{unit_id}/{year}/{module_id}/equipment/{equipment_id}",
    response_model=EquipmentDetailResponse,
)
async def get_equipment(
    unit_id: str,
    year: int,
    module_id: str,
    equipment_id: int,
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
        f"GET equipment: unit_id={unit_id}, year={year}, "
        f"module_id={module_id}, equipment_id={equipment_id}"
    )

    equipment = await equipment_service.get_equipment_by_id(
        session=db,
        equipment_id=equipment_id,
    )

    return equipment


@router.patch(
    "/{unit_id}/{year}/{module_id}/equipment/{equipment_id}",
    response_model=EquipmentDetailResponse,
)
async def update_equipment(
    unit_id: str,
    year: int,
    module_id: str,
    equipment_id: int,
    equipment_data: EquipmentUpdateRequest,
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
        f"PATCH equipment: unit_id={unit_id}, year={year}, "
        f"module_id={module_id}, equipment_id={equipment_id}, user={current_user.id}"
    )

    equipment = await equipment_service.update_equipment(
        session=db,
        equipment_id=equipment_id,
        equipment_data=equipment_data,
        user_id=current_user.id,
    )

    logger.info(f"Updated equipment {equipment_id}")

    return equipment


@router.delete(
    "/{unit_id}/{year}/{module_id}/equipment/{equipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_equipment(
    unit_id: str,
    year: int,
    module_id: str,
    equipment_id: int,
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
        f"DELETE equipment: unit_id={unit_id}, year={year}, "
        f"module_id={module_id}, equipment_id={equipment_id}, user={current_user.id}"
    )

    await equipment_service.delete_equipment(
        session=db,
        equipment_id=equipment_id,
        user_id=current_user.id,
    )

    logger.info(f"Deleted equipment {equipment_id}")
