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
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import (
    check_module_permission as _check_module_permission,
)
from app.core.policy import (
    get_module_permission_decision,
)
from app.core.role_priority import pick_role_for_institutional_id
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import (
    MODULE_TYPE_TO_DATA_ENTRY_TYPES,
    ModuleTypeEnum,
)
from app.models.unit import Unit
from app.models.user import GlobalScope, RoleName, User
from app.modules.headcount.schemas import (
    HeadcountItemResponse,
    HeadcountMemberDropdownItem,
)
from app.schemas.carbon_report import CarbonReportModuleRead
from app.schemas.carbon_report_response import (
    ModuleResponse,
    ModuleTotals,
    SubmoduleResponse,
)
from app.schemas.data_entry import (
    DataEntryResponse,
)
from app.schemas.user import UserRead
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.utils.request_context import extract_ip_address, extract_route_payload
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow
from app.workflows.embodied_energy import EmbodiedEnergyWorkflow

logger = get_logger(__name__)
router = APIRouter()

# TODO: don't forget to update stats of carbon_report_module
# on batch/create/update/delete


async def get_carbon_report(
    unit_id: int,
    year: int,
    module_type_id: ModuleTypeEnum,
    db: AsyncSession,
) -> CarbonReportModuleRead:
    """Helper to get carbon report module from unit and year."""
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
    return carbon_report_module


async def get_request_context(request: Request) -> dict:
    """Helper to extract request context for logging and auditing."""
    # This function can be expanded to include more contextual information as needed
    return {
        "ip_address": extract_ip_address(request),
        "route_path": request.url.path,
        "route_payload": await extract_route_payload(request),
    }


async def get_carbon_report_id(
    unit_id: int,
    year: int,
    module_type_id: ModuleTypeEnum,
    db: AsyncSession,
) -> int:
    """Helper to get carbon report module ID from unit and year."""
    carbon_report_module = await get_carbon_report(
        unit_id=unit_id,
        year=year,
        module_type_id=module_type_id,
        db=db,
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


# Configuration for the generic top-class breakdown endpoint.
# Maps module type → JSON data field to group by.
_MODULE_TOP_CLASS_GROUP_FIELD: dict[ModuleTypeEnum, str] = {
    ModuleTypeEnum.equipment_electric_consumption: "equipment_class",
    ModuleTypeEnum.purchase: "purchase_institutional_description",
}


@router.get(
    "/{unit_id}/{year}/{module_id}/top-class-breakdown",
)
async def get_top_class_breakdown(
    unit_id: int,
    year: int,
    module_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List:
    """Get emissions aggregated by subcategory with top 3 items per subcategory.

    Returns a list per subcategory, each containing the top 3 items (by
    emission) and a "rest" bucket. Works for any module configured in
    ``_MODULE_TOP_CLASS_GROUP_FIELD``.
    """
    await _check_module_permission(current_user, module_id, "view")

    module_key = module_id.replace("-", "_")
    module_type = ModuleTypeEnum[module_key]

    group_field = _MODULE_TOP_CLASS_GROUP_FIELD.get(module_type)
    if group_field is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Top-class breakdown not supported for module '{module_id}'",
        )

    carbon_report_module_id = await get_carbon_report_id(
        unit_id=unit_id,
        year=year,
        module_type_id=module_type,
        db=db,
    )

    data_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])

    stats = await DataEntryEmissionService(db).get_top_class_breakdown(
        carbon_report_module_id=carbon_report_module_id,
        data_entry_types=data_entry_types,
        group_by_field=group_field,
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
        Users with headcount access for this unit receive the full list;
        users with only professional_travel access receive only their own record.
    """
    # Gate: must have headcount.view OR professional_travel.view to call this endpoint
    travel_decision = await get_module_permission_decision(
        current_user, "professional-travel", "view"
    )
    headcount_decision = await get_module_permission_decision(
        current_user, "headcount", "view"
    )
    # Allow global-scope users (superadmin/backoffice) regardless of module permissions.
    # This prevents global roles from being blocked by the module-level gate while
    # still enforcing module permissions for non-global users.
    is_global = any(isinstance(r.on, GlobalScope) for r in current_user.roles)
    if not (
        is_global or headcount_decision.get("allow") or travel_decision.get("allow")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: headcount.view or professional_travel.view "
            "required",
        )

    # Data-level scope: determine the user's effective role FOR THIS SPECIFIC UNIT.
    # `get_module_permission_decision` uses calculate_user_permissions which is
    # scope-blind (a principal for unit A would appear to have headcount.view for
    # unit B too).  We instead check the unit's own institutional_id directly.
    unit = await db.get(Unit, unit_id)
    unit_iid = unit.institutional_id if unit else None

    # Full access: global roles or principal of this specific unit.
    # NOTE: having headcount.view permission alone does NOT grant full access —
    # that permission is scope-blind (a principal for unit A also appears to have
    # headcount.view for unit B). The role check below is the authoritative guard.
    has_full_access = any(
        isinstance(r.on, GlobalScope) for r in current_user.roles
    ) or (
        unit_iid is not None
        and pick_role_for_institutional_id(current_user.roles, unit_iid)
        == RoleName.CO2_USER_PRINCIPAL
    )

    carbon_report_module_id = await get_carbon_report_id(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum.headcount,
        db=db,
    )
    data_entry_service = DataEntryService(db)
    if has_full_access:
        rows = await data_entry_service.get_headcount_members(
            carbon_report_module_id=carbon_report_module_id,
        )
        return [HeadcountMemberDropdownItem(**row) for row in rows]

    # Standard / travel-only user: fetch only their own record
    user_iid = current_user.institutional_id
    if not user_iid:
        return []
    row = await data_entry_service.get_member_by_institutional_id(
        carbon_report_module_id=carbon_report_module_id,
        institutional_id=user_iid,
    )
    if row is None:
        return []
    return [HeadcountMemberDropdownItem(**row)]


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
        request_context=await get_request_context(request),
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
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user ID is required to create item",
        )
    await _check_module_permission(current_user, module_id, "edit")

    module_key = module_id.replace("-", "_")
    module_type_id = ModuleTypeEnum[module_key].value
    submodule_key = submodule_id.replace("-", "_")
    data_entry_type_id = DataEntryTypeEnum[submodule_key].value
    carbon_report_module = await get_carbon_report(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum(module_type_id),
        db=db,
    )
    if carbon_report_module is None:
        raise HTTPException(
            status_code=500,
            detail="Carbon report module could not be determined",
        )

    logger.info(
        f"POST item: unit_id={sanitize(unit_id)}, year={sanitize(year)}, "
        f"module_id={sanitize(module_id)}, user={sanitize(current_user.id)}"
    )

    submodule_key = submodule_id.replace("-", "_")
    data_entry_type = DataEntryTypeEnum[submodule_key]
    data_entry_type_id = data_entry_type.value
    request_context = await get_request_context(request)

    response = await CarbonReportModuleWorkflow(db).create(
        carbon_report_module=carbon_report_module,
        data_entry_type_id=data_entry_type_id,
        item_data=item_data,
        current_user=UserRead.model_validate(current_user),
        request_context=request_context,
        background_tasks=background_tasks,
    )
    await EmbodiedEnergyWorkflow(db).post_create(
        carbon_report_module,
        response,
        current_user=UserRead.model_validate(current_user),
        request_context=request_context,
        background_tasks=background_tasks,
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
    carbon_report_module = await get_carbon_report(
        unit_id=unit_id,
        year=year,
        module_type_id=ModuleTypeEnum[module_key],
        db=db,
    )

    request_context = await get_request_context(request)

    response = await CarbonReportModuleWorkflow(db).update(
        carbon_report_module=carbon_report_module,
        data_entry_type_id=data_entry_type_id,
        item_id=item_id,
        item_data=item_data,
        current_user=UserRead.model_validate(current_user),
        request_context=request_context,
        background_tasks=background_tasks,
    )
    await EmbodiedEnergyWorkflow(db).post_update(
        carbon_report_module,
        response,
        current_user=UserRead.model_validate(current_user),
        request_context=request_context,
        background_tasks=background_tasks,
    )
    return response


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
        carbon_report_module = await get_carbon_report(
            unit_id=unit_id,
            year=year,
            module_type_id=ModuleTypeEnum[module_key],
            db=db,
        )
        request_context = await get_request_context(request)

        await CarbonReportModuleWorkflow(db).delete(
            carbon_report_module=carbon_report_module,
            data_entry_id=item_id,
            current_user=UserRead.model_validate(current_user),
            request_context=request_context,
            background_tasks=background_tasks,
        )
        await EmbodiedEnergyWorkflow(db).post_delete(
            carbon_report_module,
            item_id,
            current_user=UserRead.model_validate(current_user),
            request_context=request_context,
            background_tasks=background_tasks,
        )
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
