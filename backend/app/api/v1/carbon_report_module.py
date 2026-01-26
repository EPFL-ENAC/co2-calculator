"""Unit Results API endpoints."""

from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import check_module_permission as _check_module_permission
from app.models.data_entry_type import DataEntryTypeEnum
from app.models.data_ingestion import IngestionMethod
from app.models.headcount import (
    HeadCountCreate,
    HeadCountCreateRequest,
    HeadcountItemResponse,
    HeadCountUpdate,
    HeadCountUpdateRequest,
)
from app.models.module_type import ModuleTypeEnum
from app.models.professional_travel import (
    ProfessionalTravelCreate,
    ProfessionalTravelItemResponse,
    ProfessionalTravelUpdate,
)
from app.models.user import User
from app.schemas.carbon_report_response import ModuleResponse, SubmoduleResponse
from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponse,
    DataEntryUpdate,
    unflatten_data_entry_payload,
)
from app.schemas.equipment import (
    EquipmentDetailResponse,
)
from app.services import equipment_service
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_service import DataEntryService
from app.services.headcount_service import HeadcountService
from app.services.professional_travel_service import ProfessionalTravelService

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
    if module_id == "equipment-electric-consumption":
        module_data = await DataEntryService(db).get_module_data(
            carbon_report_module_id=carbon_report_module_id,
        )
    elif module_id == "my-lab":
        # Fetch real data from database
        module_data = await HeadcountService(db).get_module_data(
            unit_id=unit_id,
            year=year,
        )
        stats = await HeadcountService(db).get_module_stats(
            unit_id=unit_id,
            year=year,
            aggregate_by="function_role",
        )
        module_data.stats = stats
    elif module_id == "professional-travel":
        # Fetch real data from database
        module_data = await ProfessionalTravelService(db).get_module_data(
            unit_id=unit_id,
            year=year,
            user=current_user,
            preview_limit=preview_limit,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module {module_id} not found",
        )
    return module_data


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
    submodule_data = None
    if module_id == "equipment-electric-consumption":
        submodule_key = submodule_id.replace("-", "_")
        data_entry_type_id = DataEntryTypeEnum[submodule_key].value
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
    elif module_id == "my-lab":
        submodule_data = await HeadcountService(db).get_submodule_data(
            unit_id=unit_id,
            year=year,
            submodule_key=submodule_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )
    elif module_id == "professional-travel":
        if submodule_id != "trips":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Submodule {submodule_id} not found for professional-travel",
            )
        submodule_data = await ProfessionalTravelService(db).get_submodule_data(
            unit_id=unit_id,
            year=year,
            user=current_user,
            page=page,
            limit=limit,
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
        EquipmentDetailResponse,
        HeadcountItemResponse,
        ProfessionalTravelItemResponse,
        DataEntryResponse,
    ],
    status_code=status.HTTP_201_CREATED,
)
async def create(
    unit_id: int,
    year: int,
    module_id: str,
    submodule_id: str,
    item_data: dict,  # Accept raw dict instead of Union to avoid ambiguous parsing
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
        EquipmentDetailResponse,
        HeadcountItemResponse,
        ProfessionalTravelItemResponse,
        DataEntryResponse,
    ]
    # Validate unit_id matches the one in request body
    if module_id == "equipment-electric-consumption":
        try:
            unflatten_data = unflatten_data_entry_payload(item_data)
            parsed_record = DataEntryCreate(**unflatten_data)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid item_data for creation: {str(e)}",
            )
        if current_user.id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current user ID is required to delete item",
            )
        if carbon_report_module_id is None:
            raise HTTPException(
                status_code=500,
                detail="Carbon report module ID could not be determined",
            )
        item = await DataEntryService(db).create(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=data_entry_type_id,
            user=current_user,
            data=parsed_record,
        )
        if item is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to create headcount item",
            )
        item = DataEntryResponse.model_validate(item)
    elif module_id == "my-lab":
        # Parse as HeadCountCreateRequest
        try:
            parsed_headcount = HeadCountCreateRequest(**item_data)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid item_data for headcount creation: {str(e)}",
            )
        headcount_create = HeadCountCreate(
            **parsed_headcount.dict(),
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
        if current_user.id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current user ID is required to delete item",
            )
        headcount = await HeadcountService(db).create_headcount(
            data=headcount_create,
            provider_source=IngestionMethod.manual,
            user_id=current_user.id,
        )
        if headcount is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to create headcount item",
            )
        item = HeadcountItemResponse.model_validate(headcount)
    elif module_id == "professional-travel":
        # Parse as ProfessionalTravelCreate
        try:
            parsed_travel = ProfessionalTravelCreate(**item_data)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid item_data for professional travel creation: {str(e)}",
            )
        if submodule_id != "trips":
            raise HTTPException(
                status_code=400,
                detail=f"Invalid submodule_id {submodule_id} for professional-travel",
            )
        # Ensure unit_id matches
        if parsed_travel.unit_id != unit_id:
            raise HTTPException(
                status_code=400,
                detail="unit_id in path must match unit_id in request body",
            )
        # Log user info for debugging
        logger.info(
            f"Creating professional travel: unit_id={sanitize(unit_id)}, "
            f"year={year}, user_id={sanitize(current_user.id)}, "
            f"user_email={sanitize(current_user.email)}, "
            f"traveler_name={sanitize(parsed_travel.traveler_name)}"
        )
        travel_result = await ProfessionalTravelService(db).create_travel(
            data=parsed_travel,
            user=current_user,
            year=year,
            unit_id=unit_id,
            provider_source=IngestionMethod.manual,
            provider=current_user.provider,
        )
        # Handle round trip (returns list) or single trip
        travel = travel_result[0] if isinstance(travel_result, list) else travel_result
        # Convert to item response with related data
        service = ProfessionalTravelService(db)
        item = await service._get_travel_item_response(travel, current_user)
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
    response_model=Union[
        EquipmentDetailResponse,
        HeadcountItemResponse,
        ProfessionalTravelItemResponse,
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
        EquipmentDetailResponse,
        HeadcountItemResponse,
        ProfessionalTravelItemResponse,
        DataEntryResponse,
    ]
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
    elif module_id == "professional-travel":
        if not isinstance(item_id, int):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid item_id type for professional travel retrieval",
            )
        travel = await ProfessionalTravelService(db).repo.get_by_id(
            travel_id=item_id, user=current_user
        )
        if travel is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Professional travel item not found",
            )
        service = ProfessionalTravelService(db)
        item = await service._get_travel_item_response(travel, current_user)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )
    logger.info(f"Retrieved item {sanitize(item_id)}")

    return item


@router.patch(
    "/{unit_id}/{year}/{module_id}/{submodule_id}/{item_id}",
    response_model=Union[
        EquipmentDetailResponse,
        HeadcountItemResponse,
        ProfessionalTravelItemResponse,
        DataEntryResponse,
    ],
)
async def update(
    unit_id: int,
    year: int,
    module_id: str,
    submodule_id: str,
    item_id: int,
    item_data: dict,  # Accept raw dict instead of Union to avoid ambiguous parsing
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
        EquipmentDetailResponse,
        HeadcountItemResponse,
        ProfessionalTravelItemResponse,
        DataEntryResponse,
    ]
    if module_id == "equipment-electric-consumption":
        # Parse as EquipmentUpdateRequest
        try:
            # parsed_data = EquipmentUpdateRequest(**item_data)
            transformed = unflatten_data_entry_payload(item_data)
            parsed_data = DataEntryUpdate(**transformed)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid item_data for equipment update: {str(e)}",
            )
        if current_user.id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current user ID is required to delete item",
            )
        item = await DataEntryService(db).update(
            id=item_id,
            data=parsed_data,
            user=current_user,
        )
    elif module_id == "my-lab":
        # Parse as HeadCountUpdateRequest
        try:
            parsed_headcount = HeadCountUpdateRequest(**item_data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid item_data for headcount update: {str(e)}",
            )
        updateItem = HeadCountUpdate(
            **parsed_headcount.model_dump(exclude_unset=True),
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
    elif module_id == "professional-travel":
        # Parse as ProfessionalTravelUpdate
        try:
            parsed_travel = ProfessionalTravelUpdate(**item_data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid item_data for professional travel update: {str(e)}",
            )
        travel = await ProfessionalTravelService(db).update_travel(
            travel_id=item_id,
            data=parsed_travel,
            user=current_user,
        )
        if travel is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Professional travel item not found",
            )
        service = ProfessionalTravelService(db)
        item = await service._get_travel_item_response(travel, current_user)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not supported for update",
        )
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
        if module_id == "equipment-electric-consumption":
            await DataEntryService(db).delete(
                id=item_id,
                current_user=current_user,
            )
        elif module_id == "my-lab":
            await HeadcountService(db).delete_headcount(
                headcount_id=item_id,
            )
        elif module_id == "professional-travel":
            await ProfessionalTravelService(db).delete_travel(
                travel_id=item_id,
                user=current_user,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not supported for deletion",
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
