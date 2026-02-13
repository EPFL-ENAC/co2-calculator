"""Unit Results API endpoints."""

from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import check_module_permission as _check_module_permission
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.schemas.carbon_report_response import (
    ModuleResponse,
    ModuleTotals,
    SubmoduleResponse,
)
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponse,
    DataEntryUpdate,
    HeadcountItemResponse,
    ModuleHandler,
    resolve_primary_factor_if_kind_or_subkind_changed,
)
from app.schemas.user import UserRead
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.utils.request_context import extract_ip_address, extract_route_payload

logger = get_logger(__name__)
router = APIRouter()


async def get_carbon_report_id(
    unit_id: int,
    year: int,
    module_type_id: ModuleTypeEnum,
    db: AsyncSession,
) -> int:
    """Helper to get carbon report module ID from unit and year."""
    # TODO: PLACEHOLDER UNTIL INTEGRATION WITH CARBON REPORT MODULE ID in frontend
    # find carbon_report_module_id from year/unit_id mapping:
    CarbonReportModuleService_instance = CarbonReportModuleService(db)
    carbon_report_module = (
        await CarbonReportModuleService_instance.get_carbon_report_by_year_and_unit(
            unit_id=unit_id,
            year=year,
            module_type_id=ModuleTypeEnum(module_type_id),
        )
    )
    if carbon_report_module is None or carbon_report_module.id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carbon report module not found for unit_id={unit_id}, year={year}",
        )
    return carbon_report_module.id


@router.get("/{unit_id}/{year}/{module_id}", response_model=ModuleResponse)
async def get_module(
    unit_id: int,
    year: int,
    module_id: str,  # Module identifier
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
    await _check_module_permission(current_user, module_id, "view")

    logger.info(
        f"GET module: module_id={sanitize(module_id)}, unit_id={sanitize(unit_id)}, "
        f"year={sanitize(year)}, preview_limit={sanitize(preview_limit)}"
    )
    module_key = module_id.replace("-", "_")
    # TODO: remove once migration done in frontend
    carbon_report_module_id = await get_carbon_report_id(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum[module_key],
        db=db,
    )

    if carbon_report_module_id is None:
        raise HTTPException(
            status_code=500,
            detail="Carbon report module ID could not be determined",
        )
    module_data = await DataEntryService(db).get_module_data(
        carbon_report_module_id=carbon_report_module_id,
    )

    # if headcount compute FTE here
    total_annual_fte = None
    if module_id == "headcount":
        total_annual_fte = await DataEntryService(db).get_total_per_field(
            field_name="fte",
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=None,
        )
        module_data.stats = await DataEntryService(db).get_stats(
            carbon_report_module_id=carbon_report_module_id,
            aggregate_by="function",
            aggregate_field="fte",
        )
    else:
        module_data.stats = await DataEntryEmissionService(db).get_stats(
            carbon_report_module_id=carbon_report_module_id,
        )
    # if need other subtotal do it here
    total_kg_co2eq = sum(module_data.stats.values())
    module_data.totals = ModuleTotals(
        total_kg_co2eq=total_kg_co2eq,
        total_tonnes_co2eq=total_kg_co2eq / 1000.0,
        total_annual_consumption_kwh=None,
        total_annual_fte=total_annual_fte,
    )
    if not module_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )
    return module_data


@router.get(
    "/{unit_id}/{year}/{module_id}/stats-by-class",
)
async def get_stats_by_class(
    unit_id: int,
    year: int,
    module_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List:
    """
    Get travel emissions aggregated by transport_mode and cabin_class.

    Returns treemap-format data for charts.
    """
    await _check_module_permission(current_user, module_id, "view")

    module_key = module_id.replace("-", "_")
    carbon_report_module_id = await get_carbon_report_id(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum[module_key],
        db=db,
    )

    stats = await DataEntryEmissionService(db).get_travel_stats_by_class(
        carbon_report_module_id=carbon_report_module_id,
    )
    return stats


@router.get(
    "/{unit_id}/evolution-over-time",
)
async def get_evolution_over_time(
    unit_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List:
    """
    Get travel emissions aggregated by year and transport_mode for a unit.
    """
    await _check_module_permission(current_user, "professional-travel", "view")

    stats = await DataEntryEmissionService(db).get_travel_evolution_over_time(
        unit_id=unit_id,
    )
    return stats


@router.get(
    "/{unit_id}/{year}/{module_id}/{submodule_id}",
    response_model=SubmoduleResponse,
)
async def get_submodule(
    unit_id: int,
    year: int,
    module_id: str,
    submodule_id: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=50, le=1000, description="Items per page"),
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
    await _check_module_permission(current_user, module_id, "view")

    logger.info(
        f"GET submodule: module_id={sanitize(module_id)}, "
        f"unit_id={sanitize(unit_id)}, year={sanitize(year)}, "
        f"submodule_id={sanitize(submodule_id)}, page={sanitize(page)}, "
        f"limit={sanitize(limit)}, sort_by={sanitize(sort_by)}, "
        f"sort_order={sanitize(sort_order)}"
    )

    module_key = module_id.replace("-", "_")
    # TODO: remove once migration done in frontend
    carbon_report_module_id = await get_carbon_report_id(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum[module_key],
        db=db,
    )

    # Calculate offset from page number
    offset = (page - 1) * limit

    # Fetch submodule data from database
    submodule_key = submodule_id.replace("-", "_")
    data_entry_type_id = DataEntryTypeEnum[submodule_key].value
    if data_entry_type_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submodule {submodule_id} not found",
        )
    if carbon_report_module_id is None:
        raise HTTPException(
            status_code=500,
            detail="Carbon report module ID could not be determined",
        )
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


@router.post(
    "/{unit_id}/{year}/{module_id}/{submodule_id}",
    response_model=Union[
        HeadcountItemResponse,
        DataEntryResponse,
        List[DataEntryResponse],
    ],
    status_code=status.HTTP_201_CREATED,
)
async def create(
    unit_id: int,
    year: int,
    module_id: str,
    submodule_id: str,
    item_data: dict,  # Accept raw dict instead of Union to avoid ambiguous parsing
    request: Request,
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
         with created equipment
    """
    await _check_module_permission(current_user, module_id, "edit")

    module_key = module_id.replace("-", "_")
    module_type_id = ModuleTypeEnum[module_key].value
    submodule_key = submodule_id.replace("-", "_")
    data_entry_type_id = DataEntryTypeEnum[submodule_key].value
    carbon_report_module_id = await get_carbon_report_id(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum(module_type_id),
        db=db,
    )

    logger.info(
        f"POST item: unit_id={sanitize(unit_id)}, year={sanitize(year)}, "
        f"module_id={sanitize(module_id)}, user={sanitize(current_user.id)}"
    )
    item: Union[
        HeadcountItemResponse,
        DataEntryResponse,
    ]

    submodule_key = submodule_id.replace("-", "_")
    data_entry_type = DataEntryTypeEnum[submodule_key]
    data_entry_type_id = data_entry_type.value

    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user ID is required to create item",
        )
    if carbon_report_module_id is None:
        raise HTTPException(
            status_code=500,
            detail="Carbon report module ID could not be determined",
        )

    try:
        create_payload = {
            **item_data,
            "data_entry_type_id": data_entry_type_id,
            "carbon_report_module_id": carbon_report_module_id,
        }
        handler = BaseModuleHandler.get_by_type(data_entry_type)
        create_payload = await handler.resolve_primary_factor_id(
            create_payload, data_entry_type, db
        )

        # If kind or subkind is being updated
        # we may need to resolve a new primary factor ID
        create_payload = await resolve_primary_factor_if_kind_or_subkind_changed(
            handler,
            create_payload,
            data_entry_type,
            item_data,
            existing_data={},
            db=db,
        )

        validated_data = handler.validate_create(create_payload)

        data_entry_create = DataEntryCreate(
            **validated_data.model_dump(exclude_unset=True)
        )

    except Exception as e:
        logger.error(
            "Error validating item_data for data entry creation",
            extra={"error": str(e), "item_data": sanitize(item_data)},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid item_data for creation: {str(e)}",
        )

    item = await DataEntryService(db).create(
        carbon_report_module_id=carbon_report_module_id,
        data_entry_type_id=data_entry_type_id,
        user=UserRead.model_validate(current_user),
        data=data_entry_create,
        request_context={
            "ip_address": extract_ip_address(request),
            "route_path": request.url.path,
            "route_payload": await extract_route_payload(request),
        },
    )
    if item is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to create item",
        )

    emission = await DataEntryEmissionService(db).upsert_by_data_entry(
        data_entry_response=item,
    )
    await db.commit()

    response = DataEntryResponse.model_validate(item)
    if emission and emission.meta:
        response.data = {
            **response.data,
            **emission.meta,
            "kg_co2eq": emission.kg_co2eq,
        }
    logger.info(
        f"Created {sanitize(module_id)}:{sanitize(response.id)} for {sanitize(unit_id)}"
    )

    return response


@router.get(
    "/{unit_id}/{year}/{module_id}/{submodule_id}/{item_id}",
    response_model=Union[
        HeadcountItemResponse,
        DataEntryResponse,
    ],
)
async def get(
    unit_id: int,
    year: int,
    module_id: str,
    submodule_id: str,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _check_module_permission(current_user, module_id, "view")

    logger.info(
        f"GET item: unit_id={sanitize(unit_id)}, year={sanitize(year)}, "
        f"module_id={sanitize(module_id)}, item_id={sanitize(item_id)}"
    )
    item: Union[
        HeadcountItemResponse,
        DataEntryResponse,
    ]
    if ModuleTypeEnum[module_id.replace("-", "_")] is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not supported for retrieval",
        )
    item = await DataEntryService(db).get(
        id=item_id,
    )
    logger.info(f"Retrieved item {sanitize(item_id)}")

    return item


@router.patch(
    "/{unit_id}/{year}/{module_id}/{submodule_id}/{item_id}",
    response_model=Union[
        HeadcountItemResponse,
        DataEntryResponse,
    ],
)
async def update(
    unit_id: int,
    year: int,
    module_id: str,
    # submodule_id is dataEntryType e.g 'external_clouds' or 'it'
    submodule_id: str,
    item_id: int,
    item_data: dict,  # Accept raw dict instead of Union to avoid ambiguous parsing
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _check_module_permission(current_user, module_id, "edit")

    logger.info(
        f"PATCH item: unit_id={sanitize(unit_id)}, "
        f"year={sanitize(year)}, module_id={sanitize(module_id)}, "
        f"item_id={sanitize(item_id)}, "
        f"user={sanitize(current_user.id)}"
    )
    item: Union[
        HeadcountItemResponse,
        DataEntryResponse,
    ]
    submodule_key = submodule_id.replace("-", "_")
    module_key = module_id.replace("-", "_")
    data_entry_type = DataEntryTypeEnum[submodule_key]
    data_entry_type_id = data_entry_type.value
    if ModuleTypeEnum[module_key] is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not supported for update",
        )
    if DataEntryTypeEnum[submodule_key] is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submodule not supported for update",
        )
    # TODO: remove once migration done in frontend
    carbon_report_module_id = await get_carbon_report_id(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum[module_key],
        db=db,
    )

    try:
        existing_entry = await DataEntryService(db).get(id=item_id)
        existing_data = existing_entry.data if existing_entry else {}
        update_payload = {
            **item_data,
            "data_entry_type_id": data_entry_type_id,
            "carbon_report_module_id": carbon_report_module_id,
        }
        handler: ModuleHandler = BaseModuleHandler.get_by_type(data_entry_type)
        # If kind or subkind is being updated
        # we may need to resolve a new primary factor ID
        update_payload = await resolve_primary_factor_if_kind_or_subkind_changed(
            handler, update_payload, data_entry_type, item_data, existing_data, db
        )
        validated_data = handler.validate_update(update_payload)

        data_entry_update = DataEntryUpdate(
            **validated_data.model_dump(exclude_unset=True)
        )
    except Exception as e:
        logger.error(
            f"Error validating update data for item_id={sanitize(item_id)}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid item_data for update: {str(e)}",
        )
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user ID is required to update item",
        )
    try:
        item = await DataEntryService(db).update(
            id=item_id,
            data=data_entry_update,
            user=UserRead.model_validate(current_user),
            request_context={
                "ip_address": extract_ip_address(request),
                "route_path": request.url.path,
                "route_payload": await extract_route_payload(request),
            },
        )
        await db.flush()
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data entry item not found",
            )
        # Recalculate emission after update
        await DataEntryEmissionService(db).upsert_by_data_entry(
            data_entry_response=item,
        )
        # upsert could fail if emission factor lookup fails, but we still want to
        # return the updated item
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Failed to update item_id={sanitize(item_id)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update data entry",
        ) from e
    logger.info(f"Updated item {sanitize(item_id)}")
    return item


@router.delete(
    "/{unit_id}/{year}/{module_id}/{submodule_id}/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete(
    unit_id: int,
    year: int,
    module_id: str,
    submodule_id: str,
    item_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _check_module_permission(current_user, module_id, "edit")

    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user ID is required to delete item",
        )
    logger.info(
        f"DELETE item: unit_id={sanitize(unit_id)}, "
        f"year={sanitize(year)}, module_id={sanitize(module_id)}, "
        f"item_id={sanitize(item_id)}, "
        f"user={sanitize(current_user.id)}"
    )
    try:
        if ModuleTypeEnum[module_id.replace("-", "_")] is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not supported for deletion",
            )

        await DataEntryService(db).delete(
            id=item_id,
            current_user=UserRead.model_validate(current_user),
            request_context={
                "ip_address": extract_ip_address(request),
                "route_path": request.url.path,
                "route_payload": await extract_route_payload(request),
            },
        )
        await db.commit()
    except HTTPException:
        # Re-raise HTTP exceptions (404, 403, etc.) from services
        raise
    except PermissionError as e:
        logger.warning(
            f"Permission error during deletion of item_id={sanitize(item_id)}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error during deletion of item_id={sanitize(item_id)}: "
            f"{str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete item: {str(e)}",
        ) from e
    logger.info(f"Deleted item {sanitize(item_id)}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
