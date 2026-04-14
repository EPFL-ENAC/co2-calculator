"""Service for year configuration management."""

from typing import Any, Dict

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import (
    MODULE_TYPE_TO_DATA_ENTRY_TYPES,
    ModuleTypeEnum,
)


def generate_default_year_config() -> Dict[str, Any]:
    """Generate default year configuration.

    Creates a default configuration with all modules and submodules enabled,
    using the ModuleTypeEnum and MODULE_TYPE_TO_DATA_ENTRY_TYPES mappings.

    Returns:
        Default year configuration dictionary.
    """
    modules: Dict[str, Any] = {}

    # Iterate over ModuleTypeEnum in definition order
    for module_type in ModuleTypeEnum:
        module_key = str(module_type.value)
        data_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])

        submodules: Dict[str, Any] = {}
        for data_entry_type in data_entry_types:
            submodule_key = str(data_entry_type.value)
            submodules[submodule_key] = {
                "enabled": True,
                "threshold": None,
            }

        modules[module_key] = {
            "enabled": True,
            "uncertainty_tag": "medium",
            "submodules": submodules,
        }

    return {
        "modules": modules,
        "reduction_objectives": {
            "files": {
                "institutional_footprint": None,
                "population_projections": None,
                "unit_scenarios": None,
            },
            "goals": [],
        },
    }


def get_module_config(
    config: Dict[str, Any], module_type: ModuleTypeEnum
) -> Dict[str, Any] | None:
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
    module_config: Dict[str, Any], data_entry_type: DataEntryTypeEnum
) -> Dict[str, Any] | None:
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


def update_module_threshold(
    config: Dict[str, Any],
    module_type: ModuleTypeEnum,
    data_entry_type: DataEntryTypeEnum,
    threshold: float | None,
) -> Dict[str, Any]:
    """Update threshold for a specific submodule.

    Args:
        config: Year configuration JSON.
        module_type: Module type.
        data_entry_type: Data entry type.
        threshold: New threshold value (None to clear).

    Returns:
        Updated configuration.
    """
    module_config = get_module_config(config, module_type)
    if not module_config:
        return config

    submodule_config = get_submodule_config(module_config, data_entry_type)
    if not submodule_config:
        return config

    submodule_config["threshold"] = threshold
    return config


def check_threshold_exceeded(
    config: Dict[str, Any],
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
