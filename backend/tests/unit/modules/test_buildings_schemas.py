"""Unit tests for BuildingRoomModuleHandler._compute_kwh_emission.

Formula: kwh = surface × kwh_per_m² × ratio
         result = kwh × ef × conversion_factor

conversion_factor rules (only applies when kwh_field == "heating_kwh_per_square_meter"):
  - emission_type.parent == heating_elec AND energy_type == "electric"
    → factor_values["conversion_factor"] or 1.0
  - emission_type.parent == heating_thermal AND energy_type == "thermal"
    → factor_values["conversion_factor"] or 1.0
  - otherwise → 0  (avoids double-counting the other heating branch)
For non-heating fields, conversion_factor is always 1.0.
"""

import pytest

from app.models.data_entry_emission import EmissionType
from app.modules.buildings.schemas import BuildingRoomModuleHandler

_HANDLER = BuildingRoomModuleHandler()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ELEC_LEAF = EmissionType.buildings__rooms__heating_elec__office
_THERMAL_LEAF = EmissionType.buildings__rooms__heating_thermal__office
_ELEC_PARENT = EmissionType.buildings__rooms__heating_elec


def _ctx(
    *,
    surface: float | None = 100.0,
    ratio: float | None = 0.5,
    emission_type: EmissionType = _ELEC_LEAF,
) -> dict:
    return {
        "room_surface_square_meter": surface,
        "room_allocation_ratio": ratio,
        "emission_type": emission_type,
    }


def _fv(
    *,
    kwh_per_m2: float | None = 10.0,
    ef: float | None = 0.2,
    energy_type: str | None = "electric",
    conversion_factor: float | None = 2.0,
    kwh_field: str = "lighting_kwh_per_square_meter",
) -> dict:
    values: dict = {
        "ef_kg_co2eq_per_kwh": ef,
        kwh_field: kwh_per_m2,
    }
    if energy_type is not None:
        values["energy_type"] = energy_type
    if conversion_factor is not None:
        values["conversion_factor"] = conversion_factor
    return values


# ---------------------------------------------------------------------------
# Non-heating kwh fields — conversion_factor is always 1.0
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwh_field,expected",
    [
        pytest.param(
            "lighting_kwh_per_square_meter",
            100.0 * 10.0 * 0.5 * 0.2 * 1.0,
            id="lighting-full",
        ),
        pytest.param(
            "cooling_kwh_per_square_meter",
            100.0 * 10.0 * 0.5 * 0.2 * 1.0,
            id="cooling-full",
        ),
        pytest.param(
            "ventilation_kwh_per_square_meter",
            100.0 * 10.0 * 0.5 * 0.2 * 1.0,
            id="ventilation-full",
        ),
    ],
)
def test_non_heating_fields_compute_correctly(kwh_field: str, expected: float) -> None:
    ctx = _ctx()
    fv = _fv(kwh_field=kwh_field)
    result = _HANDLER._compute_kwh_emission(ctx, fv, kwh_field)
    assert result == pytest.approx(expected)


def test_non_heating_ratio_defaults_to_one() -> None:
    ctx = _ctx(ratio=None)
    fv = _fv(kwh_field="lighting_kwh_per_square_meter")
    # ratio defaults to 1.0, so: 100 * 10 * 1.0 * 0.2
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "lighting_kwh_per_square_meter"
    ) == pytest.approx(200.0)


# ---------------------------------------------------------------------------
# Missing required values → None
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "surface,kwh_per_m2,ef",
    [
        pytest.param(None, 10.0, 0.2, id="missing-surface"),
        pytest.param(100.0, None, 0.2, id="missing-kwh_per_m2"),
        pytest.param(100.0, 10.0, None, id="missing-ef"),
    ],
)
def test_missing_required_value_returns_none(
    surface: float | None,
    kwh_per_m2: float | None,
    ef: float | None,
) -> None:
    ctx = _ctx(surface=surface)
    fv: dict = {
        "lighting_kwh_per_square_meter": kwh_per_m2,
        "ef_kg_co2eq_per_kwh": ef,
    }
    result = _HANDLER._compute_kwh_emission(ctx, fv, "lighting_kwh_per_square_meter")
    assert result is None


# ---------------------------------------------------------------------------
# Heating electric leaf — emission_type.parent == heating_elec
# ---------------------------------------------------------------------------


def test_heating_elec_with_conversion_factor() -> None:
    # surface=100, kwh/m2=10, ratio=0.5, ef=0.2, cf=2.0
    # kwh = 100 * 10 * 0.5 = 500
    # result = 500 * 0.2 * 2.0 = 200.0
    ctx = _ctx(emission_type=_ELEC_LEAF)
    fv = _fv(
        kwh_field="heating_kwh_per_square_meter",
        energy_type="electric",
        conversion_factor=2.0,
    )
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(200.0)


def test_heating_elec_missing_conversion_factor_defaults_to_one() -> None:
    # conversion_factor absent → defaults to 1.0
    ctx = _ctx(emission_type=_ELEC_LEAF)
    fv = _fv(
        kwh_field="heating_kwh_per_square_meter",
        energy_type="electric",
        conversion_factor=None,
    )
    # kwh = 100 * 10 * 0.5 = 500; result = 500 * 0.2 * 1.0 = 100.0
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(100.0)


def test_heating_elec_conversion_factor_none_defaults_to_one() -> None:
    # conversion_factor explicitly None in factor_values → `or 1.0` kicks in
    ctx = _ctx(emission_type=_ELEC_LEAF)
    fv = {
        "heating_kwh_per_square_meter": 10.0,
        "ef_kg_co2eq_per_kwh": 0.2,
        "energy_type": "electric",
        "conversion_factor": None,
    }
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(100.0)


def test_heating_elec_leaf_wrong_energy_type_gives_zero() -> None:
    # energy_type="thermal" on an elec leaf → neither branch matches → cf=0 → result=0
    ctx = _ctx(emission_type=_ELEC_LEAF)
    fv = _fv(
        kwh_field="heating_kwh_per_square_meter",
        energy_type="thermal",
        conversion_factor=2.0,
    )
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Heating thermal leaf — emission_type.parent == heating_thermal
# ---------------------------------------------------------------------------


def test_heating_thermal_with_conversion_factor() -> None:
    ctx = _ctx(emission_type=_THERMAL_LEAF)
    fv = _fv(
        kwh_field="heating_kwh_per_square_meter",
        energy_type="thermal",
        conversion_factor=3.0,
    )
    # kwh = 100 * 10 * 0.5 = 500; result = 500 * 0.2 * 3.0 = 300.0
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(300.0)


def test_heating_thermal_leaf_wrong_energy_type_gives_zero() -> None:
    ctx = _ctx(emission_type=_THERMAL_LEAF)
    fv = _fv(
        kwh_field="heating_kwh_per_square_meter",
        energy_type="electric",
        conversion_factor=3.0,
    )
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(0.0)


def test_heating_thermal_missing_conversion_factor_defaults_to_one() -> None:
    ctx = _ctx(emission_type=_THERMAL_LEAF)
    fv = _fv(
        kwh_field="heating_kwh_per_square_meter",
        energy_type="thermal",
        conversion_factor=None,
    )
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Heating with top-level parent (not a leaf) — parent check fails → cf=0
# ---------------------------------------------------------------------------


def test_heating_elec_top_level_emission_type_gives_zero() -> None:
    # _ELEC_PARENT.parent == buildings__rooms, not heating_elec → cf=0
    ctx = _ctx(emission_type=_ELEC_PARENT)
    fv = _fv(
        kwh_field="heating_kwh_per_square_meter",
        energy_type="electric",
        conversion_factor=2.0,
    )
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(0.0)
