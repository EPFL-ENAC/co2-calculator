"""Generic factors API endpoints.

Provides CRUD operations for factors with versioning and audit trail.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.factor import (
    FactorCreate,
    FactorResponse,
    FactorUpdate,
    FactorVersionHistory,
    RecalculationResponse,
)
from app.services.batch_recalculation_service import get_batch_recalculation_service
from app.services.factor_service import get_factor_service

router = APIRouter()


@router.get("", response_model=List[FactorResponse])
async def list_factors(
    factor_family: Optional[str] = Query(None, description="Filter by factor family"),
    variant_type_id: Optional[int] = Query(None, description="Filter by variant type"),
    include_expired: bool = Query(False, description="Include expired factors"),
    session: AsyncSession = Depends(get_db),
):
    """List all factors, optionally filtered by family or variant."""
    service = get_factor_service()

    if factor_family:
        factors = await service.list_by_family(
            session, factor_family, include_expired=include_expired
        )
    else:
        # List all families
        factors = []
        for family in ["power", "headcount", "flight", "cloud"]:
            family_factors = await service.list_by_family(
                session, family, include_expired=include_expired
            )
            factors.extend(family_factors)

    return [FactorResponse.model_validate(f) for f in factors]


@router.get("/{factor_id}", response_model=FactorResponse)
async def get_factor(
    factor_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Get a specific factor by ID."""
    service = get_factor_service()
    factor = await service.get_by_id(session, factor_id)

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    return FactorResponse.model_validate(factor)


@router.post("", response_model=FactorResponse, status_code=status.HTTP_201_CREATED)
async def create_factor(
    factor_data: FactorCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new factor."""
    service = get_factor_service()

    factor = await service.create_factor(
        session=session,
        factor_family=factor_data.factor_family,
        values=factor_data.values,
        created_by=current_user.id,
        variant_type_id=factor_data.variant_type_id,
        classification=factor_data.classification,
        unit=factor_data.unit,
        source=factor_data.source,
        meta=factor_data.meta,
        change_reason=factor_data.change_reason,
    )

    await session.commit()
    return FactorResponse.model_validate(factor)


@router.put("/{factor_id}", response_model=FactorResponse)
async def update_factor(
    factor_id: int,
    factor_data: FactorUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a factor.

    This creates a new version of the factor and expires the old one.
    Affected emissions will be marked for recalculation.
    """
    service = get_factor_service()

    factor = await service.update_factor(
        session=session,
        factor_id=factor_id,
        updated_by=current_user.id,
        values=factor_data.values,
        classification=factor_data.classification,
        unit=factor_data.unit,
        source=factor_data.source,
        meta=factor_data.meta,
        change_reason=factor_data.change_reason,
    )

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    await session.commit()
    return FactorResponse.model_validate(factor)


@router.delete("/{factor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def expire_factor(
    factor_id: int,
    change_reason: Optional[str] = Query(None, description="Reason for expiration"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Expire (soft-delete) a factor.

    The factor is not deleted, but marked as expired with valid_to set.
    """
    service = get_factor_service()

    factor = await service.expire_factor(
        session=session,
        factor_id=factor_id,
        expired_by=current_user.id,
        change_reason=change_reason,
    )

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    await session.commit()


@router.get("/{factor_id}/history", response_model=List[FactorVersionHistory])
async def get_factor_history(
    factor_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Get version history for a factor."""
    service = get_factor_service()

    # First verify factor exists
    factor = await service.get_by_id(session, factor_id)
    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    history = await service.get_version_history(session, factor_id)
    return [FactorVersionHistory(**h) for h in history]


@router.post("/{factor_id}/rollback", response_model=FactorResponse)
async def rollback_factor(
    factor_id: int,
    target_version: int = Query(..., description="Version to rollback to"),
    change_reason: Optional[str] = Query(None, description="Reason for rollback"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rollback a factor to a previous version.

    This creates a new version with the old data, not a mutation.
    """
    service = get_factor_service()

    factor = await service.rollback_factor(
        session=session,
        factor_id=factor_id,
        target_version=target_version,
        rolled_back_by=current_user.id,
        change_reason=change_reason,
    )

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} or target version {target_version} not found",
        )

    await session.commit()
    return FactorResponse.model_validate(factor)


@router.post("/{factor_id}/recalculate", response_model=RecalculationResponse)
async def recalculate_for_factor(
    factor_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger batch recalculation for all emissions using this factor.

    This marks existing emissions as non-current and recalculates with
    the current factor values.
    """
    factor_service = get_factor_service()
    batch_service = get_batch_recalculation_service()

    # Verify factor exists
    factor = await factor_service.get_by_id(session, factor_id)
    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    result = await batch_service.recalculate_for_factor(
        session=session,
        factor_id=factor_id,
    )

    return RecalculationResponse(
        status=result.status.value,
        factor_id=result.factor_id,
        total_modules=result.total_modules,
        successful=result.successful,
        failed=result.failed,
        failed_module_ids=result.failed_module_ids,
        error_messages=result.error_messages,
    )


# Power factor lookup endpoints (backward compatibility with legacy API)
@router.get(
    "/power/{variant_type_id}/classes",
    response_model=List[str],
)
async def list_power_classes(
    variant_type_id: int,
    session: AsyncSession = Depends(get_db),
):
    """List equipment classes for power factors."""
    service = get_factor_service()
    classes = await service.repo.list_power_classes(session, variant_type_id)
    return classes


@router.get(
    "/power/{variant_type_id}/class-subclass-map",
    response_model=Dict[str, List[str]],
)
async def get_power_class_subclass_map(
    variant_type_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Get class/subclass mapping for power factors."""
    service = get_factor_service()
    mapping = await service.get_class_subclass_map(session, variant_type_id)
    return mapping
