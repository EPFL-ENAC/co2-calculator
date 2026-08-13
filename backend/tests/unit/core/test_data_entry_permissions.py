"""Unit tests for the #951 hardcoded data-entry permission matrix.

Table-driven per the #951 issue matrix (docs/src/implementation-plans/
951-edit-rights-per-dataset-permissions.md), plus the resolution-precedence
and provenance-derivation rules the matrix relies on. Both IMPORTED and USER
branches are explicit field-level whitelists (confirmed 2026-08-13, incl.
the fields not literally named in the issue text — see the module docstring
for the resolved list: cabin_class, train natural_key fields,
purchase_institutional_code).
"""

import pytest

from app.core.data_entry_permissions import (
    ALWAYS_WRITABLE_FIELDS,
    Provenance,
    can_create,
    can_delete,
    editable_fields,
    is_policy_exempt,
    provenance_of,
    submodule_policies,
)
from app.models.data_entry import DataEntrySourceEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum


class TestProvenanceOf:
    def test_null_source_is_user(self):
        assert provenance_of(None) == Provenance.USER

    def test_user_manual_is_user(self):
        assert provenance_of(DataEntrySourceEnum.USER_MANUAL.value) == Provenance.USER

    @pytest.mark.parametrize(
        "source",
        [
            DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value,
            DataEntrySourceEnum.CSV_MODULE_UNIT_SPECIFIC.value,
            DataEntrySourceEnum.API_MODULE_PER_YEAR.value,
            DataEntrySourceEnum.API_MODULE_UNIT_SPECIFIC.value,
            DataEntrySourceEnum.EXTERNAL_INTEGRATION.value,
        ],
    )
    def test_any_ingestion_source_is_imported(self, source):
        assert provenance_of(source) == Provenance.IMPORTED


class TestCreateDeleteConstants:
    def test_user_can_always_create_and_delete(self):
        assert can_create(Provenance.USER) is True
        assert can_delete(Provenance.USER) is True

    def test_imported_can_never_create_or_delete(self):
        assert can_create(Provenance.IMPORTED) is False
        assert can_delete(Provenance.IMPORTED) is False


class TestPolicyExemption:
    def test_planner_kinds_are_exempt(self):
        assert is_policy_exempt(DataEntryTypeEnum.planner_purchase)
        assert is_policy_exempt(DataEntryTypeEnum.planner_purchase_budget)
        assert is_policy_exempt(DataEntryTypeEnum.planner_headcount)

    def test_embodied_energy_is_exempt(self):
        assert is_policy_exempt(DataEntryTypeEnum.building_embodied_energy)

    def test_ordinary_reporting_type_is_not_exempt(self):
        assert not is_policy_exempt(DataEntryTypeEnum.member)
        assert not is_policy_exempt(DataEntryTypeEnum.energy_combustion)


class TestEditableFieldsPrecedence:
    def test_submodule_specific_wins_over_module_wide(self):
        # purchases_centralized has its own entry, distinct from the other
        # purchase kinds sharing the module-wide entry.
        centralized = editable_fields(
            ModuleTypeEnum.purchase,
            DataEntryTypeEnum.purchases_centralized,
            Provenance.USER,
        )
        other_kind = editable_fields(
            ModuleTypeEnum.purchase, DataEntryTypeEnum.services, Provenance.USER
        )
        assert centralized == {"name", "annual_consumption"}
        assert centralized != other_kind

    def test_missing_entry_raises(self):
        with pytest.raises(KeyError):
            editable_fields(
                ModuleTypeEnum.buildings,
                DataEntryTypeEnum.building_embodied_energy,
                Provenance.USER,
            )


# #951 matrix, table-driven: (module, submodule, provenance) -> expected editable fields
MATRIX_CASES = [
    # Headcount
    (
        ModuleTypeEnum.headcount,
        DataEntryTypeEnum.member,
        Provenance.USER,
        {"name", "sius_code", "fte"},
    ),
    (ModuleTypeEnum.headcount, DataEntryTypeEnum.member, Provenance.IMPORTED, set()),
    (
        ModuleTypeEnum.headcount,
        DataEntryTypeEnum.student,
        Provenance.USER,
        {"fte"},
    ),
    # Process emissions
    (
        ModuleTypeEnum.process_emissions,
        DataEntryTypeEnum.process_emissions,
        Provenance.USER,
        {"category", "subcategory", "quantity"},
    ),
    (
        ModuleTypeEnum.process_emissions,
        DataEntryTypeEnum.process_emissions,
        Provenance.IMPORTED,
        set(),
    ),
    # Buildings - combustion
    (
        ModuleTypeEnum.buildings,
        DataEntryTypeEnum.energy_combustion,
        Provenance.USER,
        {"name", "quantity"},
    ),
    (
        ModuleTypeEnum.buildings,
        DataEntryTypeEnum.energy_combustion,
        Provenance.IMPORTED,
        set(),
    ),
    # Buildings - rooms
    (
        ModuleTypeEnum.buildings,
        DataEntryTypeEnum.building,
        Provenance.USER,
        {"building_name", "room_name", "room_type", "room_allocation_ratio"},
    ),
    (ModuleTypeEnum.buildings, DataEntryTypeEnum.building, Provenance.IMPORTED, set()),
    # Equipment (module-wide across scientific/it/other) — "name" excluded (locked)
    (
        ModuleTypeEnum.equipment,
        DataEntryTypeEnum.scientific,
        Provenance.USER,
        {
            "equipment_class",
            "sub_class",
            "active_usage_hours_per_week",
            "standby_usage_hours_per_week",
        },
    ),
    (
        ModuleTypeEnum.equipment,
        DataEntryTypeEnum.it,
        Provenance.IMPORTED,
        {
            "sub_class",
            "active_usage_hours_per_week",
            "standby_usage_hours_per_week",
        },
    ),
    # External Cloud
    (
        ModuleTypeEnum.external_cloud_and_ai,
        DataEntryTypeEnum.external_clouds,
        Provenance.USER,
        {"provider", "service_type", "spent_amount", "currency"},
    ),
    (
        ModuleTypeEnum.external_cloud_and_ai,
        DataEntryTypeEnum.external_clouds,
        Provenance.IMPORTED,
        set(),
    ),
    # External AI
    (
        ModuleTypeEnum.external_cloud_and_ai,
        DataEntryTypeEnum.external_ai,
        Provenance.USER,
        {"provider", "usage_type", "fte_count", "requests_per_user_per_day"},
    ),
    # Prof travel - plane (cabin_class included; user_institutional_id/"Traveler"
    # excluded — Create-only field, no Update DTO path for anyone)
    (
        ModuleTypeEnum.professional_travel,
        DataEntryTypeEnum.plane,
        Provenance.USER,
        {
            "origin_iata",
            "destination_iata",
            "departure_date",
            "number_of_trips",
            "cabin_class",
        },
    ),
    (
        ModuleTypeEnum.professional_travel,
        DataEntryTypeEnum.plane,
        Provenance.IMPORTED,
        set(),
    ),
    # Prof travel - train (natural_key fields travel with origin/destination name)
    (
        ModuleTypeEnum.professional_travel,
        DataEntryTypeEnum.train,
        Provenance.USER,
        {
            "origin_name",
            "destination_name",
            "origin_natural_key",
            "destination_natural_key",
            "departure_date",
            "number_of_trips",
            "cabin_class",
        },
    ),
    # Purchase (module-wide) — purchase_institutional_code is "UNSPSC description"
    (
        ModuleTypeEnum.purchase,
        DataEntryTypeEnum.services,
        Provenance.USER,
        {
            "name",
            "supplier",
            "quantity",
            "total_spent_amount",
            "currency",
            "purchase_institutional_code",
        },
    ),
    (ModuleTypeEnum.purchase, DataEntryTypeEnum.services, Provenance.IMPORTED, set()),
    # Purchase - centralized
    (
        ModuleTypeEnum.purchase,
        DataEntryTypeEnum.purchases_centralized,
        Provenance.USER,
        {"name", "annual_consumption"},
    ),
    # Research facilities (module-wide) — animal's researchfacility_type excluded
    (
        ModuleTypeEnum.research_facilities,
        DataEntryTypeEnum.research_facilities,
        Provenance.USER,
        {"researchfacility_id", "researchfacility_name", "use", "use_unit"},
    ),
    (
        ModuleTypeEnum.research_facilities,
        DataEntryTypeEnum.animal_facilities,
        Provenance.USER,
        {"researchfacility_id", "researchfacility_name", "use", "use_unit"},
    ),
    (
        ModuleTypeEnum.research_facilities,
        DataEntryTypeEnum.animal_facilities,
        Provenance.IMPORTED,
        set(),
    ),
]


@pytest.mark.parametrize(
    "module_type,data_entry_type,provenance,expected", MATRIX_CASES
)
def test_matrix_row(module_type, data_entry_type, provenance, expected):
    assert editable_fields(module_type, data_entry_type, provenance) == frozenset(
        expected
    )


def test_note_is_always_writable_and_not_in_any_matrix_entry():
    assert ALWAYS_WRITABLE_FIELDS == frozenset({"note"})
    for _, _, _, expected in MATRIX_CASES:
        assert "note" not in expected


class TestSubmodulePolicies:
    def test_equipment_carries_both_branches(self):
        policies = submodule_policies(DataEntryTypeEnum.scientific)
        assert policies == {
            "user": {
                "create": True,
                "delete": True,
                "editable_fields": sorted(
                    {
                        "equipment_class",
                        "sub_class",
                        "active_usage_hours_per_week",
                        "standby_usage_hours_per_week",
                        "note",
                    }
                ),
            },
            "imported": {
                "create": False,
                "delete": False,
                # note is always writable even though it's not a matrix
                # entry — the API includes it so the frontend needs no
                # separate "note is special" rule.
                "editable_fields": sorted(
                    {
                        "sub_class",
                        "active_usage_hours_per_week",
                        "standby_usage_hours_per_week",
                        "note",
                    }
                ),
            },
        }

    def test_exempt_type_returns_none(self):
        assert submodule_policies(DataEntryTypeEnum.planner_purchase) is None
        assert submodule_policies(DataEntryTypeEnum.building_embodied_energy) is None
