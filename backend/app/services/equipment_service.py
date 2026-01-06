"""Equipment service for business logic and data transformation."""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.repositories import equipment_repo
from app.repositories.power_factor_repo import PowerFactorRepository
from app.schemas.equipment import (
    EquipmentCreateRequest,
    EquipmentDetailResponse,
    EquipmentItemResponse,
    EquipmentUpdateRequest,
    ModuleResponse,
    ModuleTotals,
    SubmoduleResponse,
    SubmoduleSummary,
)
from app.services.calculation_service import calculate_equipment_emission_versioned

logger = get_logger(__name__)


# Submodule display names
SUBMODULE_NAMES = {
    "scientific": "Scientific",
    "it": "IT",
    "other": "Other",
}


async def get_module_stats(
    session: AsyncSession, unit_id: str, aggregate_by: str = "submodule"
) -> dict[str, float]:
    """Get module statistics such as total items and submodules."""
    # GOAL return total items and submodules for equipment module
    # data should be aggregated by aggregate_by param
    # {"scientific": 10, "it": 5, ...}
    # or {"laptop": 15, "server": 20, ...}
    return await equipment_repo.get_module_stats(
        session=session, unit_id=unit_id, aggregate_by=aggregate_by
    )


async def get_module_data(
    session: AsyncSession,
    unit_id: str,
    year: int,
    preview_limit: Optional[int] = None,
) -> ModuleResponse:
    """
    Get complete module data with all submodules.

    Args:
        session: Database session
        unit_id: Unit ID to filter equipment
        year: Year for the data (currently informational only)
        preview_limit: Optional limit for items per submodule

    Returns:
        ModuleResponse with all submodules and their equipment
    """
    logger.info(
        f"Fetching module data for unit={unit_id}, year={year}, "
        f"preview_limit={preview_limit}"
    )

    # Get summary statistics by submodule
    summary_by_submodule = await equipment_repo.get_equipment_summary_by_submodule(
        session, unit_id=unit_id, status="In service"
    )

    submodules = {}

    # Process each submodule
    for submodule_key in ["scientific", "it", "other"]:
        # Get summary for this submodule
        submodule_summary_data = summary_by_submodule.get(
            submodule_key,
            {
                "total_items": 0,
                "annual_consumption_kwh": 0.0,
                "total_kg_co2eq": 0.0,
            },
        )

        summary = SubmoduleSummary(**submodule_summary_data)
        total_count = submodule_summary_data["total_items"]

        # When preview_limit=0, skip item fetching and return empty items array
        if preview_limit == 0:
            items: List[EquipmentItemResponse] = []
            has_more = False
        else:
            # Get equipment for this submodule
            (
                equipment_emissions,
                total_count,
            ) = await equipment_repo.get_equipment_with_emissions(
                session,
                unit_id=unit_id,
                status="In service",
                submodule=submodule_key,
                limit=preview_limit,
                offset=0,
            )

            # Transform to response items
            items = []
            for equipment, emission, power_factor in equipment_emissions:
                assert equipment.id is not None
                item = EquipmentItemResponse(
                    id=equipment.id,
                    name=equipment.name,
                    category=equipment.category,
                    submodule=equipment.submodule,
                    equipment_class=equipment.equipment_class,
                    sub_class=equipment.sub_class,
                    act_usage=equipment.active_usage_pct or 0,
                    pas_usage=equipment.passive_usage_pct or 0,
                    standby_power_w=power_factor.standby_power_w
                    if power_factor
                    else None,
                    active_power_w=power_factor.active_power_w
                    if power_factor
                    else None,
                    status=equipment.status,
                    kg_co2eq=emission.kg_co2eq,
                    t_co2eq=round(emission.kg_co2eq / 1000.0),
                    annual_kwh=emission.annual_kwh,
                )
                items.append(item)

            # Determine if there are more items
            has_more = preview_limit is not None and total_count > preview_limit

        # Create submodule response
        submodule_id = f"{submodule_key}"
        submodule_response = SubmoduleResponse(
            id=submodule_id,
            name=SUBMODULE_NAMES.get(submodule_key, submodule_key.title()),
            count=total_count,
            items=items,
            summary=summary,
            has_more=has_more,
        )

        submodules[submodule_id] = submodule_response

    # Calculate module totals using SQL summaries (not Python sums)
    total_submodules = len(submodules)
    total_items = sum(
        summary_by_submodule.get(k, {}).get("total_items", 0)
        for k in ["scientific", "it", "other"]
    )
    total_kwh = sum(
        summary_by_submodule.get(k, {}).get("annual_consumption_kwh", 0.0)
        for k in ["scientific", "it", "other"]
    )
    total_co2 = sum(
        summary_by_submodule.get(k, {}).get("total_kg_co2eq", 0.0)
        for k in ["scientific", "it", "other"]
    )

    totals = ModuleTotals(
        total_submodules=total_submodules,
        total_items=total_items,
        total_annual_consumption_kwh=round(total_kwh, 2),
        total_kg_co2eq=round(total_co2, 2),
        total_annual_fte=None,  # FTE not applicable for equipment
    )

    # Create module response
    module_response = ModuleResponse(
        module_type="equipment-electric-consumption",
        unit="kWh",
        stats=None,
        year=year,
        retrieved_at=datetime.now(timezone.utc),
        submodules=submodules,
        totals=totals,
    )

    logger.info(
        f"Module data retrieved: {total_items} items across "
        f"{total_submodules} submodules"
    )

    return module_response


async def get_submodule_data(
    session: AsyncSession,
    unit_id: str,
    submodule_key: str,
    limit: int = 100,
    offset: int = 0,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    filter: Optional[str] = None,
) -> SubmoduleResponse:
    """
    Get paginated data for a single submodule.

    Args:
        session: Database session
        unit_id: Unit ID to filter equipment
        submodule_key: Submodule identifier (e.g., 'scientific', 'it', 'other')
        limit: Maximum number of items to return
        offset: Number of items to skip
        sort_by: Field name to sort by (e.g., 'id', 'name', 'kg_co2eq', 'annual_kwh')
        sort_order: Sort order ('asc' or 'desc'), defaults to 'asc'

    Returns:
        SubmoduleResponse with paginated equipment items
    """
    logger.info(
        f"Fetching submodule data: unit={unit_id}, "
        f"submodule={submodule_key}, limit={limit}, offset={offset}, "
        f"sort_by={sort_by}, sort_order={sort_order}"
    )

    if sort_order not in ("asc", "desc"):
        sort_order = "asc"

    # Get equipment for this submodule
    (
        equipment_emissions,
        total_count,
    ) = await equipment_repo.get_equipment_with_emissions(
        session,
        unit_id=unit_id,
        status="In service",
        submodule=submodule_key,
        limit=limit,
        offset=offset,
        sort_by=sanitize(sort_by),
        sort_order=sanitize(sort_order),
        filter=filter,
    )

    # Transform to response items
    items = []
    for equipment, emission, power_factor in equipment_emissions:
        assert equipment.id is not None
        item = EquipmentItemResponse(
            id=equipment.id,
            name=equipment.name,
            category=equipment.category,
            submodule=equipment.submodule,
            equipment_class=equipment.equipment_class,
            sub_class=equipment.sub_class,
            act_usage=equipment.active_usage_pct or 0,
            pas_usage=equipment.passive_usage_pct or 0,
            standby_power_w=power_factor.standby_power_w if power_factor else None,
            active_power_w=power_factor.active_power_w if power_factor else None,
            status=equipment.status,
            kg_co2eq=emission.kg_co2eq,
            t_co2eq=round(emission.kg_co2eq / 1000.0),
            annual_kwh=emission.annual_kwh,
        )
        items.append(item)

    # Get summary for this submodule
    summary_by_submodule = await equipment_repo.get_equipment_summary_by_submodule(
        session, unit_id=unit_id, status="In service"
    )

    submodule_summary_data = summary_by_submodule.get(
        submodule_key,
        {
            "total_items": total_count,
            "annual_consumption_kwh": 0.0,
            "total_kg_co2eq": 0.0,
        },
    )

    summary = SubmoduleSummary(**submodule_summary_data)

    # Determine if there are more items
    has_more = (offset + len(items)) < total_count

    # Create submodule response
    submodule_id = f"{submodule_key}"
    submodule_response = SubmoduleResponse(
        id=submodule_id,
        name=SUBMODULE_NAMES.get(submodule_key, submodule_key.title()),
        count=total_count,
        items=items,
        summary=summary,
        has_more=has_more,
    )

    logger.info(
        f"Submodule data retrieved: {len(items)} items "
        f"(total: {total_count}, offset: {offset})"
    )

    return submodule_response


async def get_equipment_by_id(
    session: AsyncSession,
    item_id: int,
) -> EquipmentDetailResponse:
    """
    Get equipment by ID.

    Args:
        session: Database session
        equipment_id: Equipment ID

    Returns:
        EquipmentDetailResponse

    Raises:
        HTTPException: If equipment not found
    """
    equipment = await equipment_repo.get_by_id(session, item_id)

    if not equipment:
        raise HTTPException(
            status_code=404,
            detail=f"Equipment with id {item_id} not found",
        )

    # Map database fields to response schema
    response_data = {
        "id": equipment.id,
        "cost_center": equipment.cost_center,
        "unit_id": equipment.unit_id,
        "name": equipment.name,
        "category": equipment.category,
        "submodule": equipment.submodule,
        "equipment_class": equipment.equipment_class,
        "sub_class": equipment.sub_class,
        "act_usage": equipment.active_usage_pct,
        "pas_usage": equipment.passive_usage_pct,
        "power_factor_id": equipment.power_factor_id,
        "status": equipment.status,
        "service_date": equipment.service_date,
        "cost_center_description": equipment.cost_center_description,
        "equipment_metadata": equipment.equipment_metadata,
        "created_at": equipment.created_at,
        "updated_at": equipment.updated_at,
        "created_by": equipment.created_by,
        "updated_by": equipment.updated_by,
    }

    return EquipmentDetailResponse.model_validate(response_data)


async def create_equipment(
    session: AsyncSession,
    equipment_data: EquipmentCreateRequest,
    user_id: str,
) -> EquipmentDetailResponse:
    """
    Create new equipment.

    Args:
        session: Database session
        equipment_data: Equipment creation data
        user_id: ID of user creating the equipment

    Returns:
        EquipmentDetailResponse
    """
    # Convert request to dict and prepare for database
    data_dict = equipment_data.model_dump(by_alias=False, exclude_unset=True)

    # Set cost_center to unit_id if not provided
    if "cost_center" not in data_dict or not data_dict["cost_center"]:
        data_dict["cost_center"] = data_dict["unit_id"]

    # Map fields to database column names
    field_mapping = {
        "act_usage": "active_usage_pct",
        "pas_usage": "passive_usage_pct",
        "act_power": "active_power_w",
        "pas_power": "standby_power_w",
        "metadata": "equipment_metadata",
    }

    for old_key, new_key in field_mapping.items():
        if old_key in data_dict:
            data_dict[new_key] = data_dict.pop(old_key)

    # Resolve power_factor_id if equipment_class is provided
    if "equipment_class" in data_dict and data_dict["equipment_class"]:
        equipment_class = data_dict["equipment_class"]
        sub_class = data_dict.get("sub_class")
        submodule = data_dict.get("submodule")

        if submodule and equipment_class:
            # Look up the power factor
            pf_repo = PowerFactorRepository()
            power_factor = await pf_repo.get_power_factor(
                session, submodule, equipment_class, sub_class
            )

            if not power_factor:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"No power factor found for submodule='{submodule}', "
                        f"class='{equipment_class}', sub_class='{sub_class}'"
                    ),
                )

            # Set the resolved power_factor_id and power values
            data_dict["power_factor_id"] = power_factor.id
            data_dict["active_power_w"] = power_factor.active_power_w
            data_dict["standby_power_w"] = power_factor.standby_power_w

    # Add audit fields
    data_dict["created_by"] = user_id
    data_dict["updated_by"] = user_id

    equipment = await equipment_repo.create_equipment(session, data_dict)

    logger.info(f"Created equipment {equipment.id} by user {user_id}")

    # Map database fields to response schema
    response_data = {
        "id": equipment.id,
        "cost_center": equipment.cost_center,
        "unit_id": equipment.unit_id,
        "name": equipment.name,
        "category": equipment.category,
        "submodule": equipment.submodule,
        "equipment_class": equipment.equipment_class,
        "sub_class": equipment.sub_class,
        "act_usage": equipment.active_usage_pct,
        "pas_usage": equipment.passive_usage_pct,
        "power_factor_id": equipment.power_factor_id,
        "status": equipment.status,
        "service_date": equipment.service_date,
        "cost_center_description": equipment.cost_center_description,
        "equipment_metadata": equipment.equipment_metadata,
        "created_at": equipment.created_at,
        "updated_at": equipment.updated_at,
        "created_by": equipment.created_by,
        "updated_by": equipment.updated_by,
    }

    # Synchronously compute and persist current emission row
    # settings = get_settings()
    ef = await equipment_repo.get_current_emission_factor(
        session, factor_name="swiss_electricity_mix"
    )
    if ef:
        ef_id, ef_value = ef
        # Ensure equipment has a concrete ID for emission linking
        if equipment.id is None:
            raise HTTPException(
                status_code=500,
                detail="Equipment ID missing after create",
            )
        if equipment.power_factor_id is None:
            raise HTTPException(
                status_code=500,
                detail="Power factor ID missing for emission calculation",
            )
        power_factor = await PowerFactorRepository().get_by_version_id(
            session, equipment.power_factor_id
        )
        if not power_factor:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Power factor with id {equipment.power_factor_id} "
                    "not found for emission calculation"
                ),
            )
        calc_payload = calculate_equipment_emission_versioned(
            {
                "act_usage": equipment.active_usage_pct or 0,
                "pas_usage": equipment.passive_usage_pct or 0,
                "active_power_w": getattr(power_factor, "active_power_w", 0) or 0,
                "standby_power_w": getattr(power_factor, "standby_power_w", 0) or 0,
                "status": equipment.status,
            },
            emission_factor=ef_value,
            emission_factor_id=ef_id,
            power_factor_id=equipment.power_factor_id,
        )
        await equipment_repo.insert_emission(session, equipment.id, calc_payload)

    return EquipmentDetailResponse.model_validate(response_data)


async def update_equipment(
    session: AsyncSession,
    item_id: int,
    item_data: EquipmentUpdateRequest,
    user_id: str,
) -> EquipmentDetailResponse:
    """
    Update existing equipment.

    Args:
        session: Database session
        equipment_id: Equipment ID to update
        equipment_data: Equipment update data
        user_id: ID of user updating the equipment

    Returns:
        EquipmentDetailResponse

    Raises:
        HTTPException: If equipment not found
    """
    # Get existing equipment
    equipment = await equipment_repo.get_by_id(session, item_id)

    if not equipment:
        raise HTTPException(
            status_code=404,
            detail=f"Equipment with id {item_id} not found",
        )

    # Convert request to dict, excluding unset fields
    update_dict = item_data.model_dump(by_alias=False, exclude_unset=True)

    # Map fields to database column names
    field_mapping = {
        "act_usage": "active_usage_pct",
        "pas_usage": "passive_usage_pct",
        "metadata": "equipment_metadata",
    }

    for old_key, new_key in field_mapping.items():
        if old_key in update_dict:
            update_dict[new_key] = update_dict.pop(old_key)

    # Resolve power_factor_id if equipment_class or sub_class changed
    class_changed = "equipment_class" in update_dict
    subclass_changed = "sub_class" in update_dict

    if class_changed or subclass_changed:
        # Get the values to use for lookup (new if provided, else existing)
        equipment_class = update_dict.get("equipment_class", equipment.equipment_class)
        sub_class = update_dict.get("sub_class", equipment.sub_class)
        submodule = update_dict.get("submodule", equipment.submodule)

        # Look up the power factor
        pf_repo = PowerFactorRepository()
        power_factor = await pf_repo.get_power_factor(
            session, submodule, equipment_class, sub_class
        )

        if not power_factor:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"No power factor found for submodule='{submodule}', "
                    f"class='{equipment_class}', sub_class='{sub_class}'"
                ),
            )

        # Set the resolved power_factor_id and power values
        update_dict["power_factor_id"] = power_factor.id
        update_dict["active_power_w"] = power_factor.active_power_w
        update_dict["standby_power_w"] = power_factor.standby_power_w

    # Add audit field
    update_dict["updated_by"] = user_id

    updated_equipment = await equipment_repo.update_equipment(
        session, equipment, update_dict
    )

    logger.info(
        "Updated equipment",
        extra={"equipment_id": sanitize(item_id), "user_id": sanitize(user_id)},
    )

    # Map database fields to response schema
    response_data = {
        "id": updated_equipment.id,
        "cost_center": updated_equipment.cost_center,
        "unit_id": updated_equipment.unit_id,
        "name": updated_equipment.name,
        "category": updated_equipment.category,
        "submodule": updated_equipment.submodule,
        "equipment_class": updated_equipment.equipment_class,
        "sub_class": updated_equipment.sub_class,
        "act_usage": updated_equipment.active_usage_pct,
        "pas_usage": updated_equipment.passive_usage_pct,
        "power_factor_id": updated_equipment.power_factor_id,
        "status": updated_equipment.status,
        "service_date": updated_equipment.service_date,
        "cost_center_description": updated_equipment.cost_center_description,
        "equipment_metadata": updated_equipment.equipment_metadata,
        "created_at": updated_equipment.created_at,
        "updated_at": updated_equipment.updated_at,
        "created_by": updated_equipment.created_by,
        "updated_by": updated_equipment.updated_by,
    }

    # Synchronously retire previous emission and insert a new current one
    ef = await equipment_repo.get_current_emission_factor(
        session, factor_name="swiss_electricity_mix"
    )
    if ef:
        ef_id, ef_value = ef
        # Ensure updated equipment has a concrete ID
        if updated_equipment.id is None:
            raise HTTPException(
                status_code=500,
                detail="Equipment ID missing after update",
            )
        await equipment_repo.retire_current_emission(session, updated_equipment.id)
        if equipment.power_factor_id is None:
            raise HTTPException(
                status_code=500,
                detail="Power factor ID missing for emission calculation",
            )
        power_factor = await PowerFactorRepository().get_by_version_id(
            session, equipment.power_factor_id
        )
        if not power_factor:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Power factor with id {equipment.power_factor_id} "
                    "not found for emission calculation"
                ),
            )
        calc_payload = calculate_equipment_emission_versioned(
            {
                "act_usage": updated_equipment.active_usage_pct or 0,
                "pas_usage": updated_equipment.passive_usage_pct or 0,
                "active_power_w": getattr(power_factor, "active_power_w", 0) or 0,
                "standby_power_w": getattr(power_factor, "standby_power_w", 0) or 0,
                "status": updated_equipment.status,
            },
            emission_factor=ef_value,
            emission_factor_id=ef_id,
            power_factor_id=updated_equipment.power_factor_id,
        )
        await equipment_repo.insert_emission(
            session,
            updated_equipment.id,
            calc_payload,
        )

    return EquipmentDetailResponse.model_validate(response_data)


async def delete_equipment(
    session: AsyncSession,
    equipment_id: int,
    user_id: str,
) -> None:
    """
    Delete equipment.

    Args:
        session: Database session
        equipment_id: Equipment ID to delete
        user_id: ID of user deleting the equipment

    Raises:
        HTTPException: If equipment not found
    """
    # Get existing equipment
    equipment = await equipment_repo.get_by_id(session, equipment_id)

    if not equipment:
        raise HTTPException(
            status_code=404,
            detail=f"Equipment with id {equipment_id} not found",
        )

    await equipment_repo.delete_equipment(session, equipment)

    logger.info(
        "Deleted equipment",
        extra={"equipment_id": sanitize(equipment_id), "user_id": sanitize(user_id)},
    )
