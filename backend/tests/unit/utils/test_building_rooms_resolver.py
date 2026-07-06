"""Unit tests for building-room → EmissionType resolution.

Verifies ``_resolve_building_rooms`` (used by ``resolve_emission_types`` at
runtime) emits a *single* heating leaf chosen by the matched factor's
``energy_type`` — the fix for the heating double-count (#1575). No matched
factor skips heating; a matched factor with an invalid energy_type fails loud.
"""

from unittest.mock import MagicMock

import pytest

from app.models.data_entry_emission import EmissionType
from app.models.factor import Factor
from app.utils.data_entry_emission_type_map import _resolve_building_rooms

_HEATING_LEAVES = {
    EmissionType.buildings__rooms__heating_electric,
    EmissionType.buildings__rooms__heating_thermal,
    EmissionType.buildings__rooms__heating_electric__office,
    EmissionType.buildings__rooms__heating_thermal__office,
}


def _factor(energy_type: str | None) -> Factor:
    factor = MagicMock(spec=Factor)
    factor.id = 7
    factor.classification = {"energy_type": energy_type} if energy_type else {}
    return factor


def _heating(result: list[EmissionType]) -> set[EmissionType]:
    return set(result) & _HEATING_LEAVES


def test_office_electric_emits_only_electric_leaf() -> None:
    result = _resolve_building_rooms({"room_type": "office"}, _factor("electric"))
    assert _heating(result) == {EmissionType.buildings__rooms__heating_electric__office}


def test_office_thermal_emits_only_thermal_leaf() -> None:
    result = _resolve_building_rooms({"room_type": "office"}, _factor("thermal"))
    assert _heating(result) == {EmissionType.buildings__rooms__heating_thermal__office}


def test_zz_level_electric_emits_only_electric_leaf() -> None:
    # No room_type → generic ZZ-level leaves.
    result = _resolve_building_rooms({}, _factor("electric"))
    assert _heating(result) == {EmissionType.buildings__rooms__heating_electric}


def test_never_emits_both_heating_leaves() -> None:
    # Regression #1575: the same kwh/m² must never fan out to both heating
    # branches, which double-counted heating emissions.
    for energy_type in ("electric", "thermal"):
        result = _resolve_building_rooms({"room_type": "office"}, _factor(energy_type))
        assert len(_heating(result)) == 1


def test_no_matched_factor_skips_heating() -> None:
    # None factor = no matched factor: heating is skipped, non-heating remains.
    result = _resolve_building_rooms({"room_type": "office"}, None)
    assert _heating(result) == set()
    assert EmissionType.buildings__rooms__lighting__office in result


@pytest.mark.parametrize("energy_type", [None, "", "solar", "electricity"])
def test_invalid_energy_type_fails_loud(energy_type: str | None) -> None:
    # A matched factor with a missing/unrecognized energy_type is corrupt data
    # and must raise here rather than silently drop the heating leaf (#1575).
    with pytest.raises(ValueError, match="energy_type"):
        _resolve_building_rooms({"room_type": "office"}, _factor(energy_type))
