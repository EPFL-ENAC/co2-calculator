"""CO2 calculation service for equipment energy consumption and emissions.

This service provides both simple (current/hardcoded)
and versioned calculation functions.

Versioned calculations accept factor_version and power_factor_version parameters
to support historical calculations and audit trails.
"""

from typing import Any, Dict

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def calculate_equipment_co2(
    act_usage_hrs_wk: float,
    pas_usage_hrs_wk: float,
    act_power_w: float,
    pas_power_w: float,
    emission_electric_factor: float,
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
        emission_electric_factor: Emission factor in kgCO2eq/kWh
        (e.g., 0.125 for Swiss mix)

    Returns:
        Annual CO2 emissions in kg CO2-equivalent
    """
    # Calculate weekly energy consumption in Watt-hours
    weekly_wh = (act_usage_hrs_wk * act_power_w) + (pas_usage_hrs_wk * pas_power_w)
    # Convert to annual kWh: (Wh/week * 52 weeks) / 1000
    annual_kwh = (weekly_wh * settings.WEEKS_PER_YEAR) / 1000

    # Calculate CO2 emissions
    kg_co2eq = annual_kwh * emission_electric_factor

    logger.debug(
        f"CO2 calculation: {act_usage_hrs_wk}hrs*{act_power_w}W + "
        f"{pas_usage_hrs_wk}hrs*{pas_power_w}W = {annual_kwh:.2f} kWh/year * "
        f"{emission_electric_factor} = {kg_co2eq:.2f} kgCO2eq"
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


def calculate_equipment_emission(
    equipment_data: Dict[str, Any],
    emission_electric_factor: float,
    active_power_w: float,
    standby_power_w: float,
) -> Dict[str, Any]:
    """
    Calculate equipment emission with full versioning metadata.

    This function is intended for use by background workers that persist
    calculations to the equipment_emissions table.

    Args:
        equipment_data: Dict with act_usage (hrs/wk), pas_usage (hrs/wk),
                       act_power_w, pas_power_w, status
        emission_factor: Emission factor value in kgCO2eq/kWh
        emission_factor_id: ID of the emission factor version used
        power_factor_id: ID of the power factor version used (if applicable)
        formula_version: Formula version identifier (e.g., 'v1_linear')

    Returns:
        Dict with annual_kwh, kg_co2eq, and metadata for storing in equipment_emissions
    """
    # Extract values - usage is in hours/week
    act_hrs = equipment_data.get("active_usage_hours", 0)
    pas_hrs = equipment_data.get("passive_usage_hours", 0)

    # Calculate
    annual_kwh = calculate_annual_kwh(act_hrs, pas_hrs, active_power_w, standby_power_w)
    kg_co2eq = calculate_equipment_co2(
        act_hrs,
        pas_hrs,
        active_power_w,
        standby_power_w,
        emission_electric_factor,
    )

    # Return with metadata
    return {
        "annual_kwh": annual_kwh,
        "kg_co2eq": kg_co2eq,
    }
