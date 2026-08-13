"""#951 data-entry permissions: which fields of an imported vs manually-added
row a principal/standard user may edit, and whether a row is deletable.

Hardcoded, provenance-keyed, no DB (see implementation plan for the
rationale — docs/src/implementation-plans/951-edit-rights-per-dataset-permissions.md).
Enforced in ``CarbonReportModuleWorkflow.update``/``.delete``; ``.create``
only needs the create/delete constants below, not a matrix lookup, since
manual creates are always user-branch and the module's own Create DTO is
already the correct field scope for that (see plan).

Both branches — IMPORTED (locked) and USER (a user's own row) — are field-
level whitelists per the literal #951 issue table, confirmed 2026-08-13.
"""

from enum import Enum

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import (
    MODULE_TYPE_TO_DATA_ENTRY_TYPES,
    ModuleTypeEnum,
    get_module_type_for_data_entry_type,
)
from app.schemas.data_entry import BaseModuleHandler


class Provenance(str, Enum):
    USER = "user"  # source is None or USER_MANUAL
    IMPORTED = "imported"  # any CSV_* / API_* / EXTERNAL_INTEGRATION


def provenance_of(source: int | None) -> Provenance:
    if source is None or source == 0:  # DataEntrySourceEnum.USER_MANUAL == 0
        return Provenance.USER
    return Provenance.IMPORTED


# create/delete are not stored per module: per the #951 matrix, user rows are
# ALWAYS manually addable and deletable, imported rows NEVER are — no module
# is an exception. Only which fields are updatable varies per module.
def can_create(provenance: Provenance) -> bool:
    return provenance == Provenance.USER


def can_delete(provenance: Provenance) -> bool:
    return provenance == Provenance.USER


ALWAYS_WRITABLE_FIELDS = frozenset({"note"})

# Data-entry types that never go through this policy layer: planner
# (simulator "what-if") snapshot rows, and system-derived rows created as a
# side effect of another mutation (embodied energy, from room changes).
# Neither is in the #951 matrix.
SYSTEM_MANAGED_TYPES = frozenset({DataEntryTypeEnum.building_embodied_energy})


def is_policy_exempt(data_entry_type: DataEntryTypeEnum) -> bool:
    return data_entry_type.is_planner_kind or data_entry_type in SYSTEM_MANAGED_TYPES


# (module, submodule-or-None, provenance) -> updatable field set. ``None``
# submodule = applies to every data_entry_type of that module unless a more
# specific (module, submodule, provenance) entry exists (needed for
# Buildings, Purchase-centralized, and each Travel mode). Missing entry =
# import-time error (see _validate_registry), not a silent lock.
#
# Fields NOT named in the #951 issue text, resolved 2026-08-13:
#   - cabin_class: editable (plane + train) — travel-detail field, in scope.
#   - train origin_natural_key/destination_natural_key: editable — paired
#     with origin_name/destination_name in the station picker; locking one
#     without the other breaks editing a train's route.
#   - purchase_institutional_code: editable — this IS "UNSPSC description".
#   - purchase_additional_code: locked — not named in the matrix.
#   - equipment "name": locked — matrix lists Class/Sub-class/Active/Standby
#     usage only.
#   - animal_facilities "researchfacility_type": locked — not named.
# Two fields the matrix DOES name but can never be granted regardless of
# this table, because they're Create-only on their DTO (no update path
# exists for anyone, not just this policy): Headcount's "SCIPER"
# (user_institutional_id) and Prof. Travel's "Traveler" (same field name).
PERMISSIONS: dict[
    tuple[ModuleTypeEnum, DataEntryTypeEnum | None, Provenance], frozenset[str] | None
] = {
    # Headcount (member)
    (ModuleTypeEnum.headcount, None, Provenance.USER): frozenset(
        {"name", "sius_code", "fte"}
    ),
    (ModuleTypeEnum.headcount, None, Provenance.IMPORTED): None,
    # Headcount - student (its own handler/DTO, EPT only)
    (
        ModuleTypeEnum.headcount,
        DataEntryTypeEnum.student,
        Provenance.USER,
    ): frozenset({"fte"}),
    (
        ModuleTypeEnum.headcount,
        DataEntryTypeEnum.student,
        Provenance.IMPORTED,
    ): None,
    # Process emissions
    (ModuleTypeEnum.process_emissions, None, Provenance.USER): frozenset(
        {"category", "subcategory", "quantity"}
    ),
    (ModuleTypeEnum.process_emissions, None, Provenance.IMPORTED): None,
    # Buildings - combustion
    (
        ModuleTypeEnum.buildings,
        DataEntryTypeEnum.energy_combustion,
        Provenance.USER,
    ): frozenset({"name", "quantity"}),
    (
        ModuleTypeEnum.buildings,
        DataEntryTypeEnum.energy_combustion,
        Provenance.IMPORTED,
    ): None,
    # Buildings - rooms
    (ModuleTypeEnum.buildings, DataEntryTypeEnum.building, Provenance.USER): frozenset(
        {"building_name", "room_name", "room_type", "room_allocation_ratio"}
    ),
    (
        ModuleTypeEnum.buildings,
        DataEntryTypeEnum.building,
        Provenance.IMPORTED,
    ): None,
    # Equipment (module-wide across scientific/it/other)
    (ModuleTypeEnum.equipment, None, Provenance.USER): frozenset(
        {
            "equipment_class",
            "sub_class",
            "active_usage_hours_per_week",
            "standby_usage_hours_per_week",
        }
    ),
    (ModuleTypeEnum.equipment, None, Provenance.IMPORTED): frozenset(
        {"sub_class", "active_usage_hours_per_week", "standby_usage_hours_per_week"}
    ),
    # External Cloud
    (
        ModuleTypeEnum.external_cloud_and_ai,
        DataEntryTypeEnum.external_clouds,
        Provenance.USER,
    ): frozenset({"provider", "service_type", "spent_amount", "currency"}),
    (
        ModuleTypeEnum.external_cloud_and_ai,
        DataEntryTypeEnum.external_clouds,
        Provenance.IMPORTED,
    ): None,
    # External AI
    (
        ModuleTypeEnum.external_cloud_and_ai,
        DataEntryTypeEnum.external_ai,
        Provenance.USER,
    ): frozenset({"provider", "usage_type", "fte_count", "requests_per_user_per_day"}),
    (
        ModuleTypeEnum.external_cloud_and_ai,
        DataEntryTypeEnum.external_ai,
        Provenance.IMPORTED,
    ): None,
    # Professional travel - plane
    (
        ModuleTypeEnum.professional_travel,
        DataEntryTypeEnum.plane,
        Provenance.USER,
    ): frozenset(
        {
            "origin_iata",
            "destination_iata",
            "departure_date",
            "number_of_trips",
            "cabin_class",
        }
    ),
    (
        ModuleTypeEnum.professional_travel,
        DataEntryTypeEnum.plane,
        Provenance.IMPORTED,
    ): None,
    # Professional travel - train
    (
        ModuleTypeEnum.professional_travel,
        DataEntryTypeEnum.train,
        Provenance.USER,
    ): frozenset(
        {
            "origin_name",
            "destination_name",
            "origin_natural_key",
            "destination_natural_key",
            "departure_date",
            "number_of_trips",
            "cabin_class",
        }
    ),
    (
        ModuleTypeEnum.professional_travel,
        DataEntryTypeEnum.train,
        Provenance.IMPORTED,
    ): None,
    # Purchase (module-wide across the 7 non-centralized kinds)
    (ModuleTypeEnum.purchase, None, Provenance.USER): frozenset(
        {
            "name",
            "supplier",
            "quantity",
            "total_spent_amount",
            "currency",
            "purchase_institutional_code",
        }
    ),
    (ModuleTypeEnum.purchase, None, Provenance.IMPORTED): None,
    # Purchase - centralized
    (
        ModuleTypeEnum.purchase,
        DataEntryTypeEnum.purchases_centralized,
        Provenance.USER,
    ): frozenset({"name", "annual_consumption"}),
    (
        ModuleTypeEnum.purchase,
        DataEntryTypeEnum.purchases_centralized,
        Provenance.IMPORTED,
    ): None,
    # Research facilities (module-wide across research_facilities/animal_facilities)
    (ModuleTypeEnum.research_facilities, None, Provenance.USER): frozenset(
        {"researchfacility_id", "researchfacility_name", "use", "use_unit"}
    ),
    (ModuleTypeEnum.research_facilities, None, Provenance.IMPORTED): None,
}


def editable_fields(
    module_type: ModuleTypeEnum,
    data_entry_type: DataEntryTypeEnum,
    provenance: Provenance,
) -> frozenset[str]:
    """Resolve the updatable field set: submodule-specific entry wins over
    the module-wide (``None``) one. Raises ``KeyError`` when neither exists
    — a coverage gap, not a silent lock (see ``_validate_registry``).
    """
    specific_key = (module_type, data_entry_type, provenance)
    if specific_key in PERMISSIONS:
        return PERMISSIONS[specific_key] or frozenset()
    wide_key = (module_type, None, provenance)
    if wide_key in PERMISSIONS:
        return PERMISSIONS[wide_key] or frozenset()
    raise KeyError(
        f"no data-entry permission entry for "
        f"{module_type}/{data_entry_type}/{provenance}"
    )


def submodule_policies(
    data_entry_type: DataEntryTypeEnum,
) -> dict[str, dict[str, object]] | None:
    """Both provenance branches for one submodule, for the frontend
    (``SubmoduleResponse.data_entry_policies``). ``None`` for exempt types —
    #951 policy doesn't apply to them.
    """
    if is_policy_exempt(data_entry_type):
        return None
    module_type = get_module_type_for_data_entry_type(data_entry_type)
    if module_type is None:
        return None
    return {
        provenance.value: {
            "create": can_create(provenance),
            "delete": can_delete(provenance),
            # note is always writable but isn't in any matrix entry (it's
            # metadata, not part of the module data) — union it in here so
            # the frontend's editability check is a plain membership test,
            # no separate "note is special" rule to duplicate.
            "editable_fields": sorted(
                editable_fields(module_type, data_entry_type, provenance)
                | ALWAYS_WRITABLE_FIELDS
            ),
        }
        for provenance in Provenance
    }


def _validate_registry() -> None:
    """Import-time self-check: every non-exempt (module, submodule) in the
    real module registry must resolve for both provenances, and every field
    name granted must be a real field on that submodule's update DTO — a
    coverage gap or a typo'd field name fails at import, not in production.
    """
    for module_type, data_entry_types in MODULE_TYPE_TO_DATA_ENTRY_TYPES.items():
        for data_entry_type in data_entry_types:
            if is_policy_exempt(data_entry_type):
                continue
            handler = BaseModuleHandler.get_by_type(data_entry_type)
            valid_fields = set(handler.update_dto.model_fields)
            for provenance in Provenance:
                fields = editable_fields(module_type, data_entry_type, provenance)
                unknown = fields - valid_fields
                if unknown:
                    raise ValueError(
                        f"data_entry_permissions: {module_type}/{data_entry_type}/"
                        f"{provenance} grants unknown field(s) {sorted(unknown)} "
                        f"(not in {handler.update_dto.__name__})"
                    )


_validate_registry()
