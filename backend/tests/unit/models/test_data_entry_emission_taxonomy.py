from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions import (
    EmissionType,
    get_children,
    get_subtree_leaves,
)
from app.modules.emissions.registry import (
    emission_type_scope,
    resolve_emission_types,
)


def test_parent_and_children_are_derived_from_enum_path():
    assert (
        EmissionType.buildings__rooms__lighting__office.parent
        is EmissionType.buildings__rooms__lighting
    )
    assert EmissionType.buildings__combustion__propane.parent is (
        EmissionType.buildings__combustion
    )
    assert EmissionType.buildings__combustion__propane in get_children(
        EmissionType.buildings__combustion
    )


def test_scope_is_derived_from_stat_bucket_membership():
    assert emission_type_scope(EmissionType.food__vegetarian) == 3
    assert emission_type_scope(EmissionType.buildings__rooms__lighting__office) == 2
    assert emission_type_scope(EmissionType.buildings__combustion__propane) == 1
    # heating_thermal rooms report under the scope-1 combustion bucket
    assert (
        emission_type_scope(EmissionType.buildings__rooms__heating_thermal__office) == 1
    )


def test_rollup_nodes_do_not_resolve_scope():
    assert emission_type_scope(EmissionType.professional_travel) is None
    assert emission_type_scope(EmissionType.buildings__rooms) is None


def test_subtree_leaves_include_new_combustion_fuels_from_enum_only():
    assert get_subtree_leaves(EmissionType.buildings__combustion) == [
        EmissionType.buildings__combustion__natural_gas.value,
        EmissionType.buildings__combustion__heating_oil.value,
        EmissionType.buildings__combustion__biomethane.value,
        EmissionType.buildings__combustion__pellets.value,
        EmissionType.buildings__combustion__forest_chips.value,
        EmissionType.buildings__combustion__wood_logs.value,
        EmissionType.buildings__combustion__propane.value,
    ]


def test_energy_combustion_propane_resolves_to_propane_leaf():
    assert resolve_emission_types(
        DataEntryTypeEnum.energy_combustion,
        {"name": "propane"},
    ) == [EmissionType.buildings__combustion__propane]
