"""Equipment repository for database operations."""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel import update as sqlmodel_update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.emission_factor import EmissionFactor, PowerFactor
from app.models.equipment import Equipment, EquipmentEmission

logger = get_logger(__name__)


async def get_module_stats(
    session: AsyncSession, unit_id: str, aggregate_by: str = "submodule"
) -> Dict[str, float]:
    """Aggregate equipment data by submodule or category."""
    return {"scientific": 42, "office": 15}  # Placeholder implementation


async def get_by_id(
    session: AsyncSession,
    equipment_id: int,
) -> Optional[Equipment]:
    """
    Get equipment by ID.

    Args:
        session: Database session
        equipment_id: Equipment ID

    Returns:
        Equipment instance or None if not found
    """
    query = select(Equipment).where(col(Equipment.id) == equipment_id)
    result = await session.execute(query)
    equipment = result.scalar_one_or_none()

    return equipment


async def create_equipment(
    session: AsyncSession,
    equipment_data: Dict[str, Any],
) -> Equipment:
    """
    Create new equipment.

    Args:
        session: Database session
        equipment_data: Equipment data dictionary

    Returns:
        Created Equipment instance
    """
    equipment = Equipment(**equipment_data)
    session.add(equipment)
    await session.commit()
    await session.refresh(equipment)

    logger.info(f"Created equipment {equipment.id}: {equipment.name}")

    return equipment


async def update_equipment(
    session: AsyncSession,
    equipment: Equipment,
    update_data: Dict[str, Any],
) -> Equipment:
    """
    Update existing equipment.

    Args:
        session: Database session
        equipment: Equipment instance to update
        update_data: Dictionary of fields to update

    Returns:
        Updated Equipment instance
    """
    for key, value in update_data.items():
        setattr(equipment, key, value)

    session.add(equipment)
    await session.commit()
    await session.refresh(equipment)

    logger.info(f"Updated equipment {equipment.id}: {equipment.name}")

    return equipment


async def delete_equipment(
    session: AsyncSession,
    equipment: Equipment,
) -> None:
    """
    Delete equipment and all related emissions.

    Args:
        session: Database session
        equipment: Equipment instance to delete
    """
    from sqlmodel import delete as sqlmodel_delete

    equipment_id = equipment.id
    equipment_name = equipment.name

    # First, delete all related equipment emissions
    delete_emissions_stmt = sqlmodel_delete(EquipmentEmission).where(
        col(EquipmentEmission.equipment_id) == equipment_id
    )
    await session.execute(delete_emissions_stmt)

    # Then delete the equipment
    await session.delete(equipment)
    await session.commit()

    logger.info(f"Deleted equipment {equipment_id}: {equipment_name} and its emissions")


async def get_equipment_with_emissions(
    session: AsyncSession,
    unit_id: Optional[str] = None,
    status: Optional[str] = "In service",
    submodule: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    filter: Optional[str] = None,
) -> Tuple[List[Tuple[Equipment, EquipmentEmission, PowerFactor]], int]:
    """
    Get equipment with their current emissions.

    Args:
        session: Database session
        unit_id: Filter by unit ID
        status: Filter by equipment status
        submodule: Filter by submodule
        limit: Maximum number of results
        offset: Number of results to skip
        sort_by: Field name to sort by (e.g., 'id', 'name', 'kg_co2eq', 'annual_kwh')
        sort_order: Sort order ('asc' or 'desc'), defaults to 'asc'

    Returns:
        Tuple of (list of (Equipment, EquipmentEmission) tuples, total_count)
    """
    # Field mapping for sortable columns
    field_mapping: Dict[str, Any] = {
        "id": col(Equipment.id),
        "name": col(Equipment.name),
        "equipment_class": col(Equipment.equipment_class),
        "sub_class": col(Equipment.sub_class),
        "act_usage": col(Equipment.active_usage_pct),
        "pas_usage": col(Equipment.passive_usage_pct),
        "submodule": col(Equipment.submodule),
        "category": col(Equipment.category),
        "status": col(Equipment.status),
        "unit_id": col(Equipment.unit_id),
        "cost_center": col(Equipment.cost_center),
        "service_date": col(Equipment.service_date),
        "active_power_w": col(PowerFactor.active_power_w),
        "standby_power_w": col(PowerFactor.standby_power_w),
        "created_at": col(Equipment.created_at),
        "updated_at": col(Equipment.updated_at),
        "kg_co2eq": col(EquipmentEmission.kg_co2eq),
        "annual_kwh": col(EquipmentEmission.annual_kwh),
        "computed_at": col(EquipmentEmission.computed_at),
    }

    # Build base query with join
    query = (
        select(Equipment, EquipmentEmission, PowerFactor)
        .join(
            EquipmentEmission,
            col(Equipment.id) == col(EquipmentEmission.equipment_id),
        )
        .outerjoin(
            PowerFactor,
            col(EquipmentEmission.power_factor_id) == col(PowerFactor.id),
        )
        .where(col(EquipmentEmission.is_current) == True)  # noqa: E712
    )

    if filter:
        filter.strip()
        # max filter for security
        if len(filter) > 100:
            filter = filter[:100]
        # check for empty or only-wildcard filters and handle accordingly.
        if filter == "" or filter == "%" or filter == "*":
            filter = None
    if filter:
        filter_pattern = f"%{filter}%"
        query = query.where((col(Equipment.name).ilike(filter_pattern)))

    # Apply filters
    if unit_id:
        query = query.where(col(Equipment.unit_id) == unit_id)
    if status:
        query = query.where(col(Equipment.status) == status)
    if submodule:
        query = query.where(col(Equipment.submodule) == submodule)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    if filter:
        count_query = count_query.where((col(Equipment.name).ilike(filter_pattern)))
    count_result = await session.execute(count_query)
    total_count = count_result.scalar() or 0

    # Apply sorting
    if sort_by and sort_by in field_mapping:
        sort_column = field_mapping[sort_by]
        if sort_order and sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # Default order by equipment class for predictable grouping
        query = query.order_by(col(Equipment.equipment_class))

    # Apply pagination
    if limit:
        query = query.limit(limit)
    query = query.offset(offset)

    # Execute query
    result = await session.execute(query)
    rows = result.all()

    equipment_emissions: List[Tuple[Equipment, EquipmentEmission, PowerFactor]] = []
    for equipment, emission, power_factor in rows:
        equipment_emissions.append((equipment, emission, power_factor))

    logger.debug(
        f"Retrieved {len(equipment_emissions)} equipment items "
        f"(total: {total_count}, offset: {offset}, limit: {limit})"
    )

    return equipment_emissions, total_count


async def get_equipment_summary_by_submodule(
    session: AsyncSession,
    unit_id: Optional[str] = None,
    status: Optional[str] = "In service",
    year: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Get aggregated summary statistics grouped by submodule.

    Args:
        session: Database session
        unit_id: Filter by unit ID
        status: Filter by equipment status
        year: Optional year to filter emissions by computed_at year

    Returns:
        Dict mapping submodule to summary stats:
        {
            "scientific": {
                "total_items": 10,
                "annual_consumption_kwh": 1500.0,
                "total_kg_co2eq": 187.5
            },
            ...
        }
    """
    # Build query with aggregation
    query = (
        select(
            Equipment.submodule,
            func.count(col(Equipment.id)).label("total_items"),
            func.sum(EquipmentEmission.annual_kwh).label("annual_consumption_kwh"),
            func.sum(EquipmentEmission.kg_co2eq).label("total_kg_co2eq"),
        )
        .join(
            EquipmentEmission,
            col(Equipment.id) == col(EquipmentEmission.equipment_id),
        )
        .where(col(EquipmentEmission.is_current) == True)  # noqa: E712
        # not always true! group_by could be by other fields
        .group_by(Equipment.submodule)
    )

    # Apply filters
    if unit_id:
        query = query.where(col(Equipment.unit_id) == unit_id)
    if status:
        query = query.where(col(Equipment.status) == status)
    if year is not None:
        # Filter by year of computed_at timestamp
        query = query.where(
            func.extract("year", col(EquipmentEmission.computed_at)) == year
        )

    # Execute query
    result = await session.execute(query)
    rows = result.all()

    # Convert to dict
    summary: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        summary[row.submodule] = {
            "total_items": int(row.total_items),
            "annual_consumption_kwh": float(row.annual_consumption_kwh or 0),
            "total_kg_co2eq": float(row.total_kg_co2eq or 0),
        }

    logger.debug(f"Retrieved summary for {len(summary)} submodules")

    return summary


async def get_equipment_count(
    session: AsyncSession,
    unit_id: Optional[str] = None,
    status: Optional[str] = "In service",
    submodule: Optional[str] = None,
) -> int:
    """
    Get total count of equipment matching filters.

    Args:
        session: Database session
        unit_id: Filter by unit ID
        status: Filter by equipment status
        submodule: Filter by submodule

    Returns:
        Total count of equipment
    """
    query = select(func.count(col(Equipment.id)))

    # Apply filters
    if unit_id:
        query = query.where(col(Equipment.unit_id) == unit_id)
    if status:
        query = query.where(col(Equipment.status) == status)
    if submodule:
        query = query.where(col(Equipment.submodule) == submodule)

    result = await session.execute(query)
    count = result.scalar() or 0

    return count


async def get_current_emission_factor(
    session: AsyncSession,
    factor_name: str = "swiss_electricity_mix",
) -> Optional[Tuple[int, float]]:
    """
    Fetch the current emission factor id and value by name.

    Returns (id, value) or None if not found.
    """
    stmt = (
        select(EmissionFactor.id, EmissionFactor.value)
        .where(col(EmissionFactor.factor_name) == factor_name)
        .where(col(EmissionFactor.valid_to).is_(None))
        .order_by(col(EmissionFactor.version).desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    if not row:
        logger.warning(f"No current emission factor found for '{factor_name}'.")
        return None
    return int(row[0]), float(row[1])


async def retire_current_emission(session: AsyncSession, equipment_id: int) -> None:
    """
    Mark the current emission row for equipment as not current.
    """

    stmt = (
        sqlmodel_update(EquipmentEmission)
        .where(col(EquipmentEmission.equipment_id) == equipment_id)
        .where(col(EquipmentEmission.is_current) == True)  # noqa: E712
        .values(is_current=False)
    )
    await session.execute(stmt)
    await session.commit()


async def insert_emission(
    session: AsyncSession,
    equipment_id: int,
    payload: Dict[str, Any],
) -> EquipmentEmission:
    """
    Insert a new current EquipmentEmission row for the given equipment.
    """
    emission = EquipmentEmission(
        equipment_id=equipment_id,
        annual_kwh=payload["annual_kwh"],
        kg_co2eq=payload["kg_co2eq"],
        emission_factor_id=payload["emission_factor_id"],
        power_factor_id=payload.get("power_factor_id"),
        formula_version=payload.get("formula_version", "v1_linear"),
        calculation_inputs=payload.get("calculation_inputs", {}),
        is_current=True,
    )
    session.add(emission)
    await session.commit()
    await session.refresh(emission)
    logger.debug(
        f"Inserted emission for equipment {equipment_id}: {emission.kg_co2eq} kgCO2eq"
    )
    return emission
