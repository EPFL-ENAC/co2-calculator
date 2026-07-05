"""Unit tests for building-room → EmissionType resolution.

Verifies ``_resolve_building_rooms`` (used by ``resolve_emission_types`` at
runtime) emits a *single* heating leaf chosen by the matched factor's
``energy_type`` — the fix for the heating double-count (#1575). An
absent/unknown ``energy_type`` skips heating rather than guessing.
"""

from app.models.data_entry_emission import EmissionType
from app.utils.data_entry_emission_type_map import _resolve_building_rooms

_HEATING_LEAVES = {
    EmissionType.buildings__rooms__heating_electric,
    EmissionType.buildings__rooms__heating_thermal,
    EmissionType.buildings__rooms__heating_electric__office,
    EmissionType.buildings__rooms__heating_thermal__office,
}


def _heating(result: list[EmissionType]) -> set[EmissionType]:
    return set(result) & _HEATING_LEAVES


def test_office_electric_emits_only_electric_leaf() -> None:
    result = _resolve_building_rooms({"room_type": "office"}, "electric")
    assert _heating(result) == {EmissionType.buildings__rooms__heating_electric__office}


def test_office_thermal_emits_only_thermal_leaf() -> None:
    result = _resolve_building_rooms({"room_type": "office"}, "thermal")
    assert _heating(result) == {EmissionType.buildings__rooms__heating_thermal__office}


def test_zz_level_electric_emits_only_electric_leaf() -> None:
    # No room_type → generic ZZ-level leaves.
    result = _resolve_building_rooms({}, "electric")
    assert _heating(result) == {EmissionType.buildings__rooms__heating_electric}


def test_never_emits_both_heating_leaves() -> None:
    # Regression #1575: the same kwh/m² must never fan out to both heating
    # branches, which double-counted heating emissions.
    for energy_type in ("electric", "thermal"):
        result = _resolve_building_rooms({"room_type": "office"}, energy_type)
        assert len(_heating(result)) == 1


def test_missing_or_unknown_energy_type_skips_heating() -> None:
    for energy_type in (None, "", "solar"):
        result = _resolve_building_rooms({"room_type": "office"}, energy_type)
        assert _heating(result) == set(), (
            f"energy_type={energy_type!r} should skip heating"
        )
        # Non-heating leaves are still produced.
        assert EmissionType.buildings__rooms__lighting__office in result
