"""Unit Results API endpoints."""

from typing import List, Optional, Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import check_module_permission as _check_module_permission
from app.models.data_entry import DataEntrySourceEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.modules.headcount.schemas import (
    HeadcountItemResponse,
    HeadcountMemberDropdownItem,
)
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
    ModuleHandler,
)
from app.schemas.user import UserRead
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.utils.request_context import extract_ip_address, extract_route_payload

logger = get_logger(__name__)
router = APIRouter()

# TODO: don't forget to update stats of carbon_report_module
# on batch/create/update/delete


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
    current_user: User = Depends(get_current_user),
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
        member_stats: dict = await DataEntryService(db).get_stats(
            carbon_report_module_id=carbon_report_module_id,
            aggregate_by="position_category",
            aggregate_field="fte",
            data_entry_type_id=DataEntryTypeEnum.member.value,
        )
        student_total: float | None = await DataEntryService(db).get_total_per_field(
            field_name="fte",
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=DataEntryTypeEnum.student.value,
        )
        module_data.stats = {**member_stats, "student": student_total}
    else:
        module_data.stats = await DataEntryEmissionService(db).get_stats(
            carbon_report_module_id=carbon_report_module_id,
        )
    # if need other subtotal do it here
    total_kg_co2eq = (
        sum(v for v in module_data.stats.values() if v is not None)
        if module_data.stats
        else None
    )
    module_data.totals = ModuleTotals(
        total_kg_co2eq=total_kg_co2eq,
        total_tonnes_co2eq=total_kg_co2eq / 1000.0
        if total_kg_co2eq is not None
        else None,
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
    current_user: User = Depends(get_current_user),
) -> List:
    """
    Get travel emissions aggregated by travel category and cabin_class.

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
    current_user: User = Depends(get_current_user),
) -> List:
    """
    Get travel emissions aggregated by year and category for a unit.
    """
    await _check_module_permission(current_user, "professional-travel", "view")

    stats = await DataEntryEmissionService(db).get_travel_evolution_over_time(
        unit_id=unit_id,
    )
    return stats


@router.get(
    "/{unit_id}/{year}/headcount/members",
    response_model=List[HeadcountMemberDropdownItem],
)
async def list_headcount_members(
    unit_id: int,
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[HeadcountMemberDropdownItem]:
    """List headcount members with an institutional ID for traveler dropdowns.

    Args:
        unit_id: Unit ID.
        year: Report year.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Members ordered by name, each with ``institutional_id`` and ``name``.
    """
    await _check_module_permission(current_user, "headcount", "view")

    carbon_report_module_id = await get_carbon_report_id(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum.headcount,
        db=db,
    )
    rows = await DataEntryService(db).get_headcount_members(
        carbon_report_module_id=carbon_report_module_id,
    )
    return [HeadcountMemberDropdownItem(**row) for row in rows]


@router.get(
    "/{unit_id}/{year}/{module_id}/{submodule_id}",
    response_model=SubmoduleResponse,
)
async def get_submodule(
    unit_id: int,
    year: int,
    module_id: str,
    submodule_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=100, le=1000, description="Items per page"),
    sort_by: str = Query(default="id", description="Field to sort by"),
    sort_order: str = Query(default="asc", description="Sort order: 'asc' or 'desc'"),
    filter: Optional[str] = Query(
        default=None, description="Filter string to search in name or display_name"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
        current_user=UserRead.model_validate(current_user),
        request_context={
            "ip_address": extract_ip_address(request),
            "route_path": request.url.path,
            "route_payload": await extract_route_payload(request),
        },
        background_tasks=background_tasks,
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


@router.get(
    "/{unit_id}/{year}/{module_id}/{submodule_id}/check-unique",
)
async def check_unique(
    unit_id: int,
    year: int,
    module_id: str,
    submodule_id: str,
    field: str = Query(..., description="JSON data field to check uniqueness for"),
    value: str = Query(..., description="Value to check"),
    exclude_id: Optional[int] = Query(
        default=None, description="Entry ID to exclude (for PATCH pre-validation)"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Check whether a data field value is unique within a submodule.

    Intended to be called from the form before submitting a PATCH (or POST)
    so the UI can surface a duplicate error before the round-trip.

    Args:
        unit_id: Unit ID.
        year: Report year.
        module_id: Module identifier.
        submodule_id: Submodule identifier.
        field: JSON key inside ``data`` to check (e.g. ``user_institutional_id``).
        value: The value that must be unique.
        exclude_id: ID of the entry being edited — excluded from the duplicate scan.

    Returns:
        ``{"unique": true}`` when the value is available,
        ``{"unique": false}`` when a conflict exists.
    """
    await _check_module_permission(current_user, module_id, "view")

    module_key = module_id.replace("-", "_")
    submodule_key = submodule_id.replace("-", "_")
    data_entry_type_id = DataEntryTypeEnum[submodule_key].value
    carbon_report_module_id = await get_carbon_report_id(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum[module_key],
        db=db,
    )

    is_unique = await DataEntryService(db).check_json_field_unique(
        carbon_report_module_id=carbon_report_module_id,
        data_entry_type_id=data_entry_type_id,
        field=field,
        value=value,
        exclude_id=exclude_id,
    )
    return {"unique": is_unique}


@router.post(
    "/{unit_id}/{year}/{module_id}/{submodule_id}",
    response_model=DataEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    unit_id: int,
    year: int,
    module_id: str,
    submodule_id: str,
    item_data: dict,  # Accept raw dict instead of Union to avoid ambiguous parsing
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

        from app.services.module_handler_service import ModuleHandlerService

        handler_service = ModuleHandlerService(db)
        create_payload = await handler_service.resolve_primary_factor_id(
            handler, create_payload, data_entry_type
        )

        validated_data = handler.validate_create(create_payload)

        data_entry_create = DataEntryCreate(
            **validated_data.model_dump(exclude_unset=True)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error validating item_data for data entry creation",
            extra={"error": str(e), "item_data": sanitize(item_data)},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid item_data for creation: {str(e)}",
        )

    if data_entry_type == DataEntryTypeEnum.member and validated_data.model_dump().get(
        "user_institutional_id"
    ):
        uid = validated_data.model_dump()["user_institutional_id"]
        is_unique = await DataEntryService(db).check_institutional_id_unique(
            carbon_report_module_id=carbon_report_module_id,
            uid=uid,
        )
        if not is_unique:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="DUPLICATE_INSTITUTIONAL_ID",
            )

    try:
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
            background_tasks=background_tasks,
            source=DataEntrySourceEnum.USER_MANUAL,
            created_by_id=current_user.id,
        )
        if item is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to create item",
            )

        await DataEntryEmissionService(db).upsert_by_data_entry(
            data_entry_response=item,
        )
        await CarbonReportModuleService(db).recompute_stats(carbon_report_module_id)
        await db.commit()
    except IntegrityError as e:
        await db.rollback()

        if "data_entries_unique_member_uid_per_module_idx" in str(e.orig):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This user institutional id already exists in this module.",
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity error.",
        ) from e

    except Exception as e:
        await db.rollback()
        logger.error(
            f"Failed to create item for module_id={sanitize(module_id)}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create data entry",
        ) from e
    response = DataEntryResponse.model_validate(item)
    # todo kg_co2eq in response is never used and can be removed, but for now set to 0
    # to avoid confusion until we clean up the schema
    response.data = {
        **response.data,
        "kg_co2eq": 0,
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
    current_user: User = Depends(get_current_user),
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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

        from app.services.module_handler_service import ModuleHandlerService

        handler_service = ModuleHandlerService(db)
        update_payload = await handler_service.resolve_primary_factor_if_changed(
            handler, update_payload, data_entry_type, item_data, existing_data
        )

        # For equipment partial PATCH, validate against merged persisted+incoming
        # values so active+standby weekly sum constraints are always enforced.
        # TODO: we should validate on merge data also for patch

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
            background_tasks=background_tasks,
            source=None,
            created_by_id=current_user.id,
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
        await CarbonReportModuleService(db).recompute_stats(carbon_report_module_id)
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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

        # Resolve module ID before deleting the entry (needed for stats recompute)
        module_key = module_id.replace("-", "_")
        carbon_report_module_id = await get_carbon_report_id(
            unit_id=unit_id,
            year=year,
            module_type_id=ModuleTypeEnum[module_key],
            db=db,
        )

        await DataEntryService(db).delete(
            id=item_id,
            current_user=UserRead.model_validate(current_user),
            request_context={
                "ip_address": extract_ip_address(request),
                "route_path": request.url.path,
                "route_payload": await extract_route_payload(request),
            },
            background_tasks=background_tasks,
        )
        await CarbonReportModuleService(db).recompute_stats(carbon_report_module_id)
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
