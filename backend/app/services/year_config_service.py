"""Service for year configuration management."""

from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import (
    MODULE_TYPE_TO_DATA_ENTRY_TYPES,
    ModuleTypeEnum,
)
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration

# #2007 — Research Facilities manual entry ships off: EPFL feeds this module
# from the platform API and CSV only, and a hand-typed row would compete with
# it. Another institution turns both boxes on from the backoffice.
MANUAL_INPUT_OFF_BY_DEFAULT: frozenset[DataEntryTypeEnum] = frozenset(
    {DataEntryTypeEnum.research_facilities, DataEntryTypeEnum.animal_facilities}
)


def generate_default_year_config() -> dict[str, Any]:
    """Generate default year configuration.

    Creates a default configuration with all modules and submodules enabled,
    using the ModuleTypeEnum and MODULE_TYPE_TO_DATA_ENTRY_TYPES mappings.
    Submodules in ``MANUAL_INPUT_OFF_BY_DEFAULT`` start with their end-user
    input form and CSV tools deactivated.

    Returns:
        Default year configuration dictionary.
    """
    modules: dict[str, Any] = {}

    # Iterate over ModuleTypeEnum in definition order
    for module_type in ModuleTypeEnum:
        module_key = str(module_type.value)
        data_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])

        submodules: dict[str, Any] = {}
        for data_entry_type in data_entry_types:
            submodule_key = str(data_entry_type.value)
            deactivated = data_entry_type in MANUAL_INPUT_OFF_BY_DEFAULT
            submodules[submodule_key] = {
                "enabled": True,
                "threshold": None,
                "inputs_deactivated": deactivated,
                "csv_deactivated": deactivated,
            }

        modules[module_key] = {
            "enabled": True,
            "uncertainty_tag": "medium",
            "submodules": submodules,
        }

    return {
        "modules": modules,
        "reduction_objectives": {
            "institutional_footprint": [],
            "population_projections": [],
            "unit_scenarios": [],
            "files": {
                "institutional_footprint": None,
                "population_projections": None,
                "unit_scenarios": None,
            },
            "goals": [],
        },
    }


def get_module_config(
    config: dict[str, Any], module_type: ModuleTypeEnum
) -> dict[str, Any] | None:
    """Get configuration for a specific module type.

    Args:
        config: Year configuration JSON.
        module_type: Module type to get config for.

    Returns:
        Module configuration or None if not found.
    """
    modules = config.get("modules", {})
    return modules.get(str(module_type.value))


def get_submodule_config(
    module_config: dict[str, Any], data_entry_type: DataEntryTypeEnum
) -> dict[str, Any] | None:
    """Get configuration for a specific submodule (data entry type).

    Args:
        module_config: Module configuration.
        data_entry_type: Data entry type to get config for.

    Returns:
        Submodule configuration or None if not found.
    """
    if not module_config:
        return None
    submodules = module_config.get("submodules", {})
    return submodules.get(str(data_entry_type.value))


def check_threshold_exceeded(
    config: dict[str, Any],
    module_type: ModuleTypeEnum,
    data_entry_type: DataEntryTypeEnum,
    value: float,
) -> bool:
    """Check if a value exceeds the configured threshold.

    Args:
        config: Year configuration JSON.
        module_type: Module type.
        data_entry_type: Data entry type.
        value: Value to check.

    Returns:
        True if threshold is exceeded, False otherwise.
    """
    submodule_config = get_submodule_config(
        get_module_config(config, module_type) or {}, data_entry_type
    )
    if not submodule_config:
        return False

    threshold = submodule_config.get("threshold")
    if threshold is None:
        return False

    return value > threshold


async def is_submodule_inputs_deactivated(
    session: AsyncSession,
    year: int,
    provider: UserProvider,
    module_type: ModuleTypeEnum,
    data_entry_type: DataEntryTypeEnum,
) -> bool:
    """Whether end-user data entry is switched off for this submodule.

    A year with no configuration row, or a submodule the backoffice has never
    touched, resolves to ``False`` — the same default ``SubmoduleConfig``
    declares. Set by the backoffice Data Management screen (#2007).
    """
    stmt = select(YearConfiguration).where(
        col(YearConfiguration.year) == year,
        col(YearConfiguration.provider) == provider,
    )
    year_config = (await session.exec(stmt)).first()
    if year_config is None or year_config.config is None:
        return False
    module_config = get_module_config(year_config.config, module_type)
    if module_config is None:
        return False
    submodule_config = get_submodule_config(module_config, data_entry_type)
    if submodule_config is None:
        return False
    return bool(submodule_config.get("inputs_deactivated", False))
