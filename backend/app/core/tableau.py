"""Modules with the Tableau import turned on (#500).

TABLEAU_MODULES lists them by module type name. Empty turns Tableau off for
the whole app. ProviderFactory.tableau_modules() also checks that each module
has a Tableau provider; the lifespan calls it, so a typo stops the startup.
"""

from app.core.config import get_settings
from app.models.module_type import ModuleTypeEnum


def configured_tableau_modules() -> frozenset[ModuleTypeEnum]:
    """Parse TABLEAU_MODULES. An unknown module name raises ValueError."""
    raw = get_settings().TABLEAU_MODULES
    modules = set()
    for name in (part.strip() for part in raw.split(",")):
        if not name:
            continue
        module = ModuleTypeEnum.__members__.get(name)
        if module is None:
            raise ValueError(f"TABLEAU_MODULES: unknown module type {name!r}")
        modules.add(module)
    return frozenset(modules)
