"""Submodule mandatoriness rules for the "Incomplete" tag (#1215).

Only ``factor`` and ``reference`` uploads are mandatory; ``data`` (CSV)
and ``api_data`` are not. Mandatoriness moved here from the frontend
constant so the backend can emit ``incomplete`` and the frontend just
renders it ("Backend is source of truth").
"""

from typing import NamedTuple


class SubmoduleMandatoriness(NamedTuple):
    """Per-submodule mandatoriness flags."""

    mandatory_factor: bool
    mandatory_reference: bool


# Keyed by (module_type_id, data_entry_type_id). Mirrors the frontend
# ``MODULE_SUBMODULES`` constant; ``noFactors`` entries are marked
# ``mandatory_factor=False`` — their factors come from a module-level
# common-factor upload (see MODULES_REQUIRING_COMMON_FACTOR).
SUBMODULE_MANDATORINESS: dict[tuple[int, int], SubmoduleMandatoriness] = {
    # Headcount
    (1, 1): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=False),
    (1, 2): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=False),
    # ProfessionalTravel — train + plane have mandatory reference
    (2, 21): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=True),
    (2, 20): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=True),
    # Buildings — building has mandatory reference; embodied energy is
    # factors-only (no separate flag needed beyond mandatory_factor=True).
    (3, 30): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=True),
    (3, 31): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=False),
    (3, 32): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=False),
    # EquipmentElectricConsumption — all submodules are noFactors; factors
    # come from the module-level common-factor upload (see
    # MODULES_REQUIRING_COMMON_FACTOR).
    (4, 10): SubmoduleMandatoriness(mandatory_factor=False, mandatory_reference=False),
    (4, 11): SubmoduleMandatoriness(mandatory_factor=False, mandatory_reference=False),
    (4, 12): SubmoduleMandatoriness(mandatory_factor=False, mandatory_reference=False),
    # Purchase — most submodules are noFactors; additional_purchases (67)
    # carries its own factors.
    (5, 60): SubmoduleMandatoriness(mandatory_factor=False, mandatory_reference=False),
    (5, 61): SubmoduleMandatoriness(mandatory_factor=False, mandatory_reference=False),
    (5, 62): SubmoduleMandatoriness(mandatory_factor=False, mandatory_reference=False),
    (5, 63): SubmoduleMandatoriness(mandatory_factor=False, mandatory_reference=False),
    (5, 64): SubmoduleMandatoriness(mandatory_factor=False, mandatory_reference=False),
    (5, 65): SubmoduleMandatoriness(mandatory_factor=False, mandatory_reference=False),
    (5, 66): SubmoduleMandatoriness(mandatory_factor=False, mandatory_reference=False),
    (5, 67): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=False),
    # ResearchFacilities
    (6, 70): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=False),
    (6, 71): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=False),
    # ExternalCloudAndAI
    (7, 40): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=False),
    (7, 41): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=False),
    # ProcessEmissions
    (8, 50): SubmoduleMandatoriness(mandatory_factor=True, mandatory_reference=False),
}


# Modules whose factor uploads live at the module level (common-factor)
# rather than per-submodule — Equipment Electric Consumption + Purchase.
# Mirrors the frontend ``MODULE_COMMON_UPLOADS`` constant.
MODULES_REQUIRING_COMMON_FACTOR: frozenset[int] = frozenset({4, 5})

_DEFAULT_MANDATORINESS = SubmoduleMandatoriness(
    mandatory_factor=False, mandatory_reference=False
)


def get_submodule_mandatoriness(
    module_type_id: int, data_entry_type_id: int
) -> SubmoduleMandatoriness:
    """Return mandatoriness for a (module, submodule) pair.

    Unknown pairs default to no mandatory uploads so an unseeded
    submodule never raises "Incomplete" by accident.
    """
    return SUBMODULE_MANDATORINESS.get(
        (module_type_id, data_entry_type_id), _DEFAULT_MANDATORINESS
    )
