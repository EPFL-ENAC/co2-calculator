"""CO2 calculation service for equipment energy consumption and emissions.

This service provides both simple (current/hardcoded)
and versioned calculation functions.

Versioned calculations accept factor_version and power_factor_version parameters
to support historical calculations and audit trails.
"""

from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def calculate_equipment_co2(
    act_usage_hrs_wk: float,
    pas_usage_hrs_wk: float,
    act_power_w: float,
    pas_power_w: float,
    emission_factor: float,
    status: str = "In service",
) -> float:
    """
    Calculate annual CO2 emissions for a single equipment item.

    Formula: kgCO2-eq = [Active Use (hrs/wk) * Active Power (W) +
                         Standby Use (hrs/wk) * Standby Power (W)] * EF * 52 wks/year

    Args:
        act_usage_hrs_wk: Active usage hours per week
        pas_usage_hrs_wk: Passive/standby usage hours per week
        act_power_w: Active power consumption in Watts
        pas_power_w: Passive/standby power consumption in Watts
        emission_factor: Emission factor in kgCO2eq/kWh (e.g., 0.125 for Swiss mix)
        status: Equipment status (only "In service" equipment contributes to emissions)

    Returns:
        Annual CO2 emissions in kg CO2-equivalent
    """
    if status != "In service":
        logger.debug(f"Equipment not in service (status={status}), returning 0 kgCO2eq")
        return 0.0

    # Calculate weekly energy consumption in Watt-hours
    weekly_wh = (act_usage_hrs_wk * act_power_w) + (pas_usage_hrs_wk * pas_power_w)

    # Convert to annual kWh: (Wh/week * 52 weeks) / 1000
    annual_kwh = (weekly_wh * settings.WEEKS_PER_YEAR) / 1000

    # Calculate CO2 emissions
    kg_co2eq = annual_kwh * emission_factor

    logger.debug(
        f"CO2 calculation: {act_usage_hrs_wk}hrs*{act_power_w}W + "
        f"{pas_usage_hrs_wk}hrs*{pas_power_w}W = {annual_kwh:.2f} kWh/year * "
        f"{emission_factor} = {kg_co2eq:.2f} kgCO2eq"
    )

    return round(kg_co2eq, 2)


def calculate_annual_kwh(
    act_usage_hrs_wk: float,
    pas_usage_hrs_wk: float,
    act_power_w: float,
    pas_power_w: float,
) -> float:
    """
    Calculate annual energy consumption in kWh for a single equipment item.

    Args:
        act_usage_hrs_wk: Active usage hours per week
        pas_usage_hrs_wk: Passive/standby usage hours per week
        act_power_w: Active power consumption in Watts
        pas_power_w: Passive/standby power consumption in Watts

    Returns:
        Annual energy consumption in kWh
    """
    weekly_wh = (act_usage_hrs_wk * act_power_w) + (pas_usage_hrs_wk * pas_power_w)
    annual_kwh = (weekly_wh * settings.WEEKS_PER_YEAR) / 1000
    return round(annual_kwh, 2)


def convert_percentage_to_hours(
    act_usage_pct: float, pas_usage_pct: float
) -> tuple[float, float]:
    """
    Convert usage percentages to hours per week.

    Assumes percentages sum to 100% and represent distribution across 168 hours/week.

    Args:
        act_usage_pct: Active usage percentage (0-100)
        pas_usage_pct: Passive usage percentage (0-100)

    Returns:
        Tuple of (active_hours_per_week, passive_hours_per_week)
    """
    total_hours = settings.HOURS_PER_WEEK
    act_hours = (act_usage_pct / 100) * total_hours
    pas_hours = (pas_usage_pct / 100) * total_hours

    logger.debug(
        f"Converted usage: {act_usage_pct}% → {act_hours}hrs, "
        f"{pas_usage_pct}% → {pas_hours}hrs"
    )

    return round(act_hours, 2), round(pas_hours, 2)


def enrich_item_with_calculations(
    item: Dict[str, Any],
    emission_factor: float | None = None,
    factor_version_id: int | None = None,
    power_factor_version_id: int | None = None,
) -> Dict[str, Any]:
    """
    Enrich an equipment item with calculated kgCO2eq and annual kWh.

    Modifies the item dict in-place and returns it.

    Args:
        item: Equipment item dict with act_usage, pas_usage, act_power, pas_power
        emission_factor: Emission factor to use (defaults to Swiss mix from settings)
        factor_version_id: ID of emission factor version used
            (for versioned calculations)
        power_factor_version_id: ID of power factor version used
            (for versioned calculations)

    Returns:
        The enriched item dict with kg_co2eq field added
    """
    if emission_factor is None:
        emission_factor = settings.EMISSION_FACTOR_SWISS_MIX

    # Get usage values - could be percentages or hours
    # For now, assume they are percentages and convert
    act_usage = item.get("act_usage", 0)
    pas_usage = item.get("pas_usage", 0)

    # If percentages, convert to hours
    if act_usage + pas_usage <= 100:
        act_hrs, pas_hrs = convert_percentage_to_hours(act_usage, pas_usage)
    else:
        # Assume already in hours
        act_hrs, pas_hrs = act_usage, pas_usage

    # Get power values
    act_power = item.get("act_power", 0)
    pas_power = item.get("pas_power", 0)

    # Get status (default to "In service")
    status = item.get("status", "In service")

    # Calculate CO2
    kg_co2eq = calculate_equipment_co2(
        act_hrs, pas_hrs, act_power, pas_power, emission_factor, status
    )

    # Add to item
    item["kg_co2eq"] = kg_co2eq

    # Optionally add version tracking metadata
    if factor_version_id is not None:
        item["_factor_version_id"] = factor_version_id
    if power_factor_version_id is not None:
        item["_power_factor_version_id"] = power_factor_version_id

    return item


def calculate_submodule_summary(
    items: List[Dict[str, Any]], emission_factor: float | None = None
) -> Dict[str, Any]:
    """
    Calculate summary statistics for a submodule's equipment items.

    Args:
        items: List of equipment item dicts
        emission_factor: Emission factor to use (defaults to Swiss mix from settings)

    Returns:
        Summary dict with total_items, annual_consumption_kwh, total_kg_co2eq
    """
    if emission_factor is None:
        emission_factor = settings.EMISSION_FACTOR_SWISS_MIX

    total_items = len(items)
    total_kwh = 0.0
    total_co2 = 0.0

    for item in items:
        # Get usage and power
        act_usage = item.get("act_usage", 0)
        pas_usage = item.get("pas_usage", 0)

        # Convert percentages to hours if needed
        if act_usage + pas_usage <= 100:
            act_hrs, pas_hrs = convert_percentage_to_hours(act_usage, pas_usage)
        else:
            act_hrs, pas_hrs = act_usage, pas_usage

        act_power = item.get("act_power", 0)
        pas_power = item.get("pas_power", 0)

        # Calculate for this item
        kwh = calculate_annual_kwh(act_hrs, pas_hrs, act_power, pas_power)
        total_kwh += kwh

        # Get CO2 from item (should already be calculated)
        total_co2 += item.get("kg_co2eq", 0)

    return {
        "total_items": total_items,
        "annual_consumption_kwh": round(total_kwh, 2),
        "total_kg_co2eq": round(total_co2, 2),
    }


def calculate_module_totals(submodules: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate total statistics across all submodules.

    Args:
        submodules: Dict of submodule data with summaries

    Returns:
        Totals dict with total_submodules, total_items,
        total_annual_consumption_kwh, total_kg_co2eq
    """
    total_submodules = len(submodules)
    total_items = 0
    total_kwh = 0.0
    total_co2 = 0.0

    for submodule in submodules.values():
        summary = submodule.get("summary", {})
        total_items += summary.get("total_items", 0)
        total_kwh += summary.get("annual_consumption_kwh", 0)
        total_co2 += summary.get("total_kg_co2eq", 0)

    return {
        "total_submodules": total_submodules,
        "total_items": total_items,
        "total_annual_consumption_kwh": round(total_kwh, 2),
        "total_kg_co2eq": round(total_co2, 2),
    }


def calculate_equipment_emission_versioned(
    equipment_data: Dict[str, Any],
    emission_factor: float,
    emission_factor_id: int,
    power_factor_id: Optional[int] = None,
    formula_version: str = "v1_linear",
) -> Dict[str, Any]:
    """
    Calculate equipment emission with full versioning metadata.

    This function is intended for use by background workers that persist
    calculations to the equipment_emissions table.

    Args:
        equipment_data: Dict with act_usage_pct, pas_usage_pct, act_power_w,
        pas_power_w,status
        emission_factor: Emission factor value in kgCO2eq/kWh
        emission_factor_id: ID of the emission factor version used
        power_factor_id: ID of the power factor version used (if applicable)
        formula_version: Formula version identifier (e.g., 'v1_linear')

    Returns:
        Dict with annual_kwh, kg_co2eq, and metadata for storing in equipment_emissions
    """
    # Extract values
    act_usage = equipment_data.get("act_usage_pct", equipment_data.get("act_usage", 0))
    pas_usage = equipment_data.get("pas_usage_pct", equipment_data.get("pas_usage", 0))

    # Convert percentages to hours
    if act_usage + pas_usage <= 100:
        act_hrs, pas_hrs = convert_percentage_to_hours(act_usage, pas_usage)
    else:
        act_hrs, pas_hrs = act_usage, pas_usage

    act_power = equipment_data.get("act_power_w", equipment_data.get("act_power", 0))
    pas_power = equipment_data.get("pas_power_w", equipment_data.get("pas_power", 0))
    status = equipment_data.get("status", "In service")

    # Calculate
    annual_kwh = calculate_annual_kwh(act_hrs, pas_hrs, act_power, pas_power)
    kg_co2eq = calculate_equipment_co2(
        act_hrs, pas_hrs, act_power, pas_power, emission_factor, status
    )

    # Return with metadata
    return {
        "annual_kwh": annual_kwh,
        "kg_co2eq": kg_co2eq,
        "emission_factor_id": emission_factor_id,
        "power_factor_id": power_factor_id,
        "formula_version": formula_version,
        "calculation_inputs": {
            "act_usage_pct": act_usage,
            "pas_usage_pct": pas_usage,
            "act_power_w": act_power,
            "pas_power_w": pas_power,
            "emission_factor": emission_factor,
            "status": status,
        },
    }
