"""Unit tests for BuildingRoomModuleHandler.

Two concerns are covered:

* ``_compute_kwh_emission`` — the arithmetic
  ``kwh = surface × kwh_per_m² × ratio``; ``result = kwh × ef × conversion_factor``.
  ``conversion_factor`` applies only to ``heating_kwh_per_square_meter`` (default
  1.0); for every other field it is 1.0. The formula no longer inspects
  ``energy_type`` — heating-leaf selection happens in ``resolve_computations``.

* ``resolve_computations`` — emits exactly one heating leaf (electric OR thermal)
  matching the factor's ``energy_type`` carried in ``ctx``; the mismatched heating
  leaf produces no computation. A missing ``primary_factor_id`` yields nothing.
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
_ELEC_ZZ = EmissionType.buildings__rooms__heating_elec
_THERMAL_ZZ = EmissionType.buildings__rooms__heating_thermal
_LIGHTING_LEAF = EmissionType.buildings__rooms__lighting__office


def _ctx(
    *,
    surface: float | None = 100.0,
    ratio: float | None = 0.5,
) -> dict:
    return {
        "room_surface_square_meter": surface,
        "room_allocation_ratio": ratio,
    }


def _fv(
    *,
    kwh_per_m2: float | None = 10.0,
    ef: float | None = 0.2,
    conversion_factor: float | None = 2.0,
    kwh_field: str = "lighting_kwh_per_square_meter",
) -> dict:
    values: dict = {
        "ef_kg_co2eq_per_kwh": ef,
        kwh_field: kwh_per_m2,
    }
    if conversion_factor is not None:
        values["conversion_factor"] = conversion_factor
    return values


# ---------------------------------------------------------------------------
# _compute_kwh_emission — non-heating fields ignore conversion_factor (1.0)
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
# _compute_kwh_emission — missing required values → None
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
# _compute_kwh_emission — heating applies conversion_factor (default 1.0)
# ---------------------------------------------------------------------------


def test_heating_applies_conversion_factor() -> None:
    # kwh = 100 * 10 * 0.5 = 500; result = 500 * 0.2 * 2.0 = 200.0
    fv = _fv(kwh_field="heating_kwh_per_square_meter", conversion_factor=2.0)
    assert _HANDLER._compute_kwh_emission(
        _ctx(), fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(200.0)


def test_heating_missing_conversion_factor_defaults_to_one() -> None:
    fv = _fv(kwh_field="heating_kwh_per_square_meter", conversion_factor=None)
    # 500 * 0.2 * 1.0 = 100.0
    assert _HANDLER._compute_kwh_emission(
        _ctx(), fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(100.0)


def test_heating_conversion_factor_none_defaults_to_one() -> None:
    # conversion_factor explicitly None in factor_values → `or 1.0` kicks in
    fv = {
        "heating_kwh_per_square_meter": 10.0,
        "ef_kg_co2eq_per_kwh": 0.2,
        "conversion_factor": None,
    }
    assert _HANDLER._compute_kwh_emission(
        _ctx(), fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# resolve_computations — heating-leaf selection by factor energy_type
# ---------------------------------------------------------------------------


def _rc_ctx(*, energy_type: str | None, factor_id: int | None = 7) -> dict:
    ctx: dict = {"energy_type": energy_type}
    if factor_id is not None:
        ctx["primary_factor_id"] = factor_id
    return ctx


@pytest.mark.parametrize(
    "leaf,energy_type,should_emit",
    [
        pytest.param(_ELEC_LEAF, "electric", True, id="ww-elec-match"),
        pytest.param(_ELEC_LEAF, "thermal", False, id="ww-elec-mismatch"),
        pytest.param(_THERMAL_LEAF, "thermal", True, id="ww-thermal-match"),
        pytest.param(_THERMAL_LEAF, "electric", False, id="ww-thermal-mismatch"),
        pytest.param(_ELEC_ZZ, "electric", True, id="zz-elec-match"),
        pytest.param(_THERMAL_ZZ, "thermal", True, id="zz-thermal-match"),
        pytest.param(_ELEC_LEAF, None, False, id="missing-energy-type"),
    ],
)
def test_resolve_computations_heating_leaf_selection(
    leaf: EmissionType, energy_type: str | None, should_emit: bool
) -> None:
    comps = _HANDLER.resolve_computations(None, leaf, _rc_ctx(energy_type=energy_type))
    if should_emit:
        assert len(comps) == 1
        assert comps[0].emission_type == leaf
        assert comps[0].factor_id == 7
    else:
        assert comps == []


def test_resolve_computations_non_heating_always_emits() -> None:
    # lighting is energy_type-independent — emitted regardless of energy_type.
    comps = _HANDLER.resolve_computations(
        None, _LIGHTING_LEAF, _rc_ctx(energy_type="thermal")
    )
    assert len(comps) == 1
    assert comps[0].emission_type == _LIGHTING_LEAF


def test_resolve_computations_missing_factor_id_returns_empty() -> None:
    comps = _HANDLER.resolve_computations(
        None, _ELEC_LEAF, _rc_ctx(energy_type="electric", factor_id=None)
    )
    assert comps == []


def test_resolve_computations_emitted_heating_formula_computes() -> None:
    # The emitted electric-heating computation, fed factor values, yields the
    # correct kg_co2eq end-to-end (resolve + formula): 500 * 0.2 * 2.0 = 200.0.
    comps = _HANDLER.resolve_computations(
        None, _ELEC_LEAF, _rc_ctx(energy_type="electric")
    )
    assert len(comps) == 1
    fv = _fv(kwh_field="heating_kwh_per_square_meter", conversion_factor=2.0)
    assert comps[0].formula_func(_ctx(), fv) == pytest.approx(200.0)
