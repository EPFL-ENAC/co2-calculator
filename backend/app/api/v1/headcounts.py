"""Headcount API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.security import require_permission
from app.models.headcount import HeadCount, HeadCountCreate, HeadCountUpdate
from app.models.user import User
from app.services.headcount_service import HeadcountService

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/units/{unit_id}/years/{year}/headcounts",
    response_model=HeadCount,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Permission denied: modules.headcount.edit required"
                    }
                }
            },
        }
    },
)
async def create_headcount(
    unit_id: int,
    year: int,
    headcount_data: HeadCountCreate,
    module_id: str = "not_defined",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("modules.headcount", "edit")),
) -> HeadCount:
    """
    Create a new headcount record.

    **Required Permission**: `modules.headcount.edit`

    **Authorization**:
    - Principals and secondaries: Can create for their assigned units
    - Backoffice admin: Can create for all units
    - Standard users: No access

    Args:
        unit_id: The unit identifier
        year: The year for the headcount
        headcount_data: The headcount data to create
        module_id: Optional module identifier (default: "not_defined")
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created headcount record

    Raises:
        403: Missing required permission or insufficient scope
        500: Failed to create headcount record
    """
    try:
        logger.info(
            f"Creating headcount for unit={sanitize(unit_id)}, year={sanitize(year)}, "
            f"module={sanitize(module_id)} by user={sanitize(current_user.id)}"
        )

        if current_user.id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current user ID is required to create headcount",
            )
        service = HeadcountService(db, user=current_user)
        headcount = await service.create_headcount(
            data=headcount_data,
            provider_source="api",
            user_id=current_user.id,
        )

        logger.info(f"Successfully created headcount id={sanitize(headcount.id)}")
        return headcount

    except Exception as e:
        logger.error(f"Error creating headcount: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create headcount record",
        )


@router.get(
    "/units/{unit_id}/years/{year}/headcounts",
    response_model=list[HeadCount],
    responses={
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Permission denied: modules.headcount.view required"
                    }
                }
            },
        }
    },
)
async def get_headcounts(
    unit_id: int,
    year: int,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "id",
    sort_order: str = "asc",
    module_id: str = "not_defined",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("modules.headcount", "view")),
) -> list[HeadCount]:
    """
    Get a list of headcount records for a specific unit and year.

    **Required Permission**: `modules.headcount.view`

    **Authorization**:
    - Principals and secondaries: Can view headcounts for their assigned units
    - Backoffice admin: Can view headcounts for all units
    - Standard users: Can view only their own headcount data

    Data is automatically filtered by user scope.

    Args:
        unit_id: The unit identifier
        year: The year for the headcounts
        limit: Maximum number of records to return
        offset: Number of records to skip
        sort_by: Field to sort by
        sort_order: Sort order ("asc" or "desc")
        module_id: Optional module identifier (default: "not_defined")
        db: Database session
        current_user: Current authenticated user

    Raises:
        403: Missing required permission
    """
    logger.info(
        f"Fetching headcounts for unit={sanitize(unit_id)}, year={sanitize(year)}, "
        f"module={sanitize(module_id)} by user={sanitize(current_user.id)}"
    )

    service = HeadcountService(db, user=current_user)
    headcounts = await service.get_headcounts(
        unit_id=unit_id,
        year=year,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    logger.info(
        f"Fetched {sanitize(len(headcounts))} headcounts for unit={sanitize(unit_id)}, "
        f"year={sanitize(year)}"
    )
    return headcounts


@router.get(
    "/units/{unit_id}/years/{year}/headcounts/{headcount_id}",
    response_model=HeadCount,
    responses={
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Permission denied: modules.headcount.view required"
                    }
                }
            },
        },
        404: {
            "description": "Headcount not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Headcount with id 123 not found"}
                }
            },
        },
    },
)
async def get_headcount(
    unit_id: int,
    year: int,
    headcount_id: int,
    module_id: str = "not_defined",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("modules.headcount", "view")),
) -> HeadCount:
    """
    Get a specific headcount record by ID.

    **Required Permission**: `modules.headcount.view`

    **Authorization**:
    - Principals and secondaries: Can view headcounts for their assigned units
    - Backoffice admin: Can view headcounts for all units
    - Standard users: Can view only their own headcount data

    Args:
        unit_id: The unit identifier
        year: The year for the headcount
        headcount_id: The headcount record ID
        module_id: Optional module identifier (default: "not_defined")
        db: Database session
        current_user: Current authenticated user

    Returns:
        Headcount record

    Raises:
        403: Missing required permission or insufficient scope
        404: Headcount not found or not accessible by user
    """
    logger.info(
        f"Fetching headcount id={sanitize(headcount_id)} for unit={sanitize(unit_id)}, "
        f"year={sanitize(year)} by user={sanitize(current_user.id)}"
    )

    service = HeadcountService(db, user=current_user)
    headcount = await service.get_by_id(headcount_id)

    if not headcount:
        logger.warning(f"Headcount id={sanitize(headcount_id)} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Headcount with id {headcount_id} not found",
        )

    # Optional: Verify unit_id matches
    if headcount.unit_id != unit_id:
        logger.warning(
            f"Unit mismatch: requested={sanitize(unit_id)},"
            f" found={sanitize(headcount.unit_id)}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Headcount not found for this unit",
        )

    return headcount


@router.patch(
    "/units/{unit_id}/years/{year}/headcounts/{headcount_id}",
    response_model=HeadCount,
    responses={
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Permission denied: modules.headcount.edit required"
                    }
                }
            },
        },
        404: {
            "description": "Headcount not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Headcount with id 123 not found"}
                }
            },
        },
    },
)
async def update_headcount(
    unit_id: int,
    year: int,
    headcount_id: int,
    headcount_data: HeadCountUpdate,
    module_id: str = "not_defined",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("modules.headcount", "edit")),
) -> HeadCount:
    """
    Update an existing headcount record.

    **Required Permission**: `modules.headcount.edit`

    **Authorization**:
    - Principals and secondaries: Can update headcounts for their assigned units
    - Backoffice admin: Can update headcounts for all units
    - Standard users: No access

    Args:
        unit_id: The unit identifier
        year: The year for the headcount
        headcount_id: The headcount record ID to update
        headcount_data: The headcount data to update
        module_id: Optional module identifier (default: "not_defined")
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated headcount record

    Raises:
        403: Missing required permission or insufficient scope
        404: Headcount not found or not accessible by user
    """
    logger.info(
        f"Updating headcount id={sanitize(headcount_id)} for unit={sanitize(unit_id)}, "
        f"year={sanitize(year)} by user={sanitize(current_user.id)}"
    )

    service = HeadcountService(db, user=current_user)
    headcount = await service.update_headcount(
        headcount_id=headcount_id,
        data=headcount_data,
        user=current_user,
    )

    if not headcount:
        logger.warning(f"Headcount id={sanitize(headcount_id)} not found for update")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Headcount with id {headcount_id} not found",
        )

    # Optional: Verify unit_id matches
    if headcount.unit_id != unit_id:
        logger.warning(
            f"Unit mismatch during update: requested={sanitize(unit_id)}, "
            f"found={sanitize(headcount.unit_id)}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Headcount not found for this unit",
        )

    logger.info(f"Successfully updated headcount id={sanitize(headcount_id)}")
    return headcount


@router.delete(
    "/units/{unit_id}/years/{year}/headcounts/{headcount_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Permission denied: modules.headcount.edit required"
                    }
                }
            },
        },
        404: {
            "description": "Headcount not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Headcount with id 123 not found"}
                }
            },
        },
    },
)
async def delete_headcount(
    unit_id: int,
    year: int,
    headcount_id: int,
    module_id: str = "not_defined",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("modules.headcount", "edit")),
) -> None:
    """
    Delete a headcount record.

    **Required Permission**: `modules.headcount.edit`

    **Authorization**:
    - Principals and secondaries: Can delete headcounts for their assigned units
    - Backoffice admin: Can delete headcounts for all units
    - Standard users: No access

    Args:
        unit_id: The unit identifier
        year: The year for the headcount
        headcount_id: The headcount record ID to delete
        module_id: Optional module identifier (default: "not_defined")
        db: Database session
        current_user: Current authenticated user

    Raises:
        403: Missing required permission or insufficient scope
        404: Headcount not found or not accessible by user
        500: Failed to delete headcount record
    """
    logger.info(
        f"Deleting headcount id={sanitize(headcount_id)} for unit={sanitize(unit_id)}, "
        f"year={sanitize(year)} by user={sanitize(current_user.id)}"
    )

    service = HeadcountService(db, user=current_user)
    # First verify the headcount exists and belongs to the unit
    headcount = await service.get_by_id(headcount_id)

    if not headcount:
        logger.warning(f"Headcount id={sanitize(headcount_id)} not found for deletion")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Headcount with id {headcount_id} not found",
        )

    # Optional: Verify unit_id matches
    if headcount.unit_id != unit_id:
        logger.warning(
            f"Unit mismatch during delete: requested={sanitize(unit_id)}, "
            f"found={sanitize(headcount.unit_id)}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Headcount not found for this unit",
        )

    # Delete headcount via service (authorization already checked at route level)
    success = await service.delete_headcount(headcount_id)

    if not success:
        logger.error(f"Failed to delete headcount id={sanitize(headcount_id)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete headcount record",
        )

    logger.info(f"Successfully deleted headcount id={sanitize(headcount_id)}")
