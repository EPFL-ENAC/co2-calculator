"""Unit tests for BuildingRoomModuleHandler._compute_kwh_emission.

Formula: kwh = surface × kwh_per_m² × ratio
         result = kwh × ef × conversion_factor

conversion_factor applies only to the heating field
("heating_kwh_per_square_meter") — it converts primary energy to final
energy — and defaults to 1.0 when absent. Which heating leaf (electric vs
thermal) is emitted is decided upstream by ``_resolve_building_rooms``, so
the formula no longer inspects energy_type. For non-heating fields,
conversion_factor is always 1.0.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry_emission import EmissionType
from app.models.factor import Factor
from app.modules.buildings.schemas import BuildingRoomModuleHandler

_HANDLER = BuildingRoomModuleHandler()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
# Heating field — conversion_factor applies (defaults to 1.0)
# ---------------------------------------------------------------------------


def test_heating_with_conversion_factor() -> None:
    # surface=100, kwh/m2=10, ratio=0.5, ef=0.2, cf=2.0
    # kwh = 100 * 10 * 0.5 = 500; result = 500 * 0.2 * 2.0 = 200.0
    ctx = _ctx()
    fv = _fv(kwh_field="heating_kwh_per_square_meter", conversion_factor=2.0)
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(200.0)


def test_heating_missing_conversion_factor_defaults_to_one() -> None:
    # conversion_factor absent → defaults to 1.0
    ctx = _ctx()
    fv = _fv(kwh_field="heating_kwh_per_square_meter", conversion_factor=None)
    # kwh = 100 * 10 * 0.5 = 500; result = 500 * 0.2 * 1.0 = 100.0
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(100.0)


def test_heating_conversion_factor_none_defaults_to_one() -> None:
    # conversion_factor explicitly None in factor_values → default 1.0
    ctx = _ctx()
    fv = {
        "heating_kwh_per_square_meter": 10.0,
        "ef_kg_co2eq_per_kwh": 0.2,
        "conversion_factor": None,
    }
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(100.0)


def test_heating_conversion_factor_zero_is_respected() -> None:
    # A legitimate conversion_factor=0.0 (e.g. carbon-free network) must zero the
    # heating emission — not be coerced to 1.0 by a falsy `or` default.
    ctx = _ctx()
    fv = _fv(kwh_field="heating_kwh_per_square_meter", conversion_factor=0.0)
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "heating_kwh_per_square_meter"
    ) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# conversion_factor is heating-only — non-heating fields ignore it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwh_field",
    [
        "lighting_kwh_per_square_meter",
        "cooling_kwh_per_square_meter",
        "ventilation_kwh_per_square_meter",
    ],
)
def test_non_heating_field_ignores_conversion_factor(kwh_field: str) -> None:
    # A non-1 conversion_factor must not affect non-heating leaves — the factor
    # only converts heating primary→final energy. Result must equal the cf=1 case.
    ctx = _ctx()
    fv = _fv(kwh_field=kwh_field, conversion_factor=5.0)
    # kwh = 100 * 10 * 0.5 = 500; result = 500 * 0.2 * 1.0 = 100.0 (cf ignored)
    assert _HANDLER._compute_kwh_emission(ctx, fv, kwh_field) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Zero is a value, not "missing" — only None short-circuits to None
# ---------------------------------------------------------------------------


def test_zero_surface_returns_zero_not_none() -> None:
    # surface=0.0 is a legitimate value (guard uses `is None`, not falsiness),
    # so the formula returns 0.0 rather than None (which means "missing input").
    ctx = _ctx(surface=0.0)
    fv = _fv(kwh_field="lighting_kwh_per_square_meter")
    assert _HANDLER._compute_kwh_emission(
        ctx, fv, "lighting_kwh_per_square_meter"
    ) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# resolve_computations — factor gating and kwh-field resolution
# ---------------------------------------------------------------------------


def test_resolve_computations_without_factor_id_returns_empty() -> None:
    # No primary_factor_id → no factor → no emission computation.
    ctx = {"room_surface_square_meter": 100.0}
    assert (
        _HANDLER.resolve_computations(
            None, EmissionType.buildings__rooms__lighting__office, ctx
        )
        == []
    )


def test_resolve_computations_heating_leaf_formula_applies_conversion_factor() -> None:
    ctx = {**_ctx(), "primary_factor_id": 5}
    comps = _HANDLER.resolve_computations(
        None, EmissionType.buildings__rooms__heating_electric, ctx
    )
    assert len(comps) == 1
    fv = _fv(kwh_field="heating_kwh_per_square_meter", conversion_factor=2.0)
    # heating leaf → heating field → cf applies: 100*10*0.5 * 0.2 * 2.0 = 200.0
    assert comps[0].formula_func(ctx, fv) == pytest.approx(200.0)


def test_resolve_computations_ww_leaf_falls_back_to_parent_kwh_field() -> None:
    # heating_electric__office is not in _EMISSION_TO_KWH_FIELD; it must resolve
    # via its parent (heating_electric) to the heating kwh field, so cf applies.
    ctx = {**_ctx(), "primary_factor_id": 5}
    comps = _HANDLER.resolve_computations(
        None, EmissionType.buildings__rooms__heating_electric__office, ctx
    )
    assert len(comps) == 1
    fv = _fv(kwh_field="heating_kwh_per_square_meter", conversion_factor=2.0)
    assert comps[0].formula_func(ctx, fv) == pytest.approx(200.0)


def test_resolve_computations_unmapped_emission_type_returns_empty() -> None:
    # The rooms rollup parent has no kwh field and its parent isn't mapped either.
    ctx = {**_ctx(), "primary_factor_id": 5}
    assert _HANDLER.resolve_computations(None, EmissionType.buildings__rooms, ctx) == []


# ---------------------------------------------------------------------------
# get_factor_for_resolve_emission_types — the factor selects the heating leaf
# ---------------------------------------------------------------------------


def _entry(data: dict) -> MagicMock:
    entry = MagicMock()
    entry.data = data
    return entry


@pytest.mark.asyncio
async def test_get_factor_reads_from_cache_without_db() -> None:
    # A prefetched cache hit resolves the factor without touching the DB.
    factor = MagicMock(spec=Factor)
    cache = {7: factor}
    result = await _HANDLER.get_factor_for_resolve_emission_types(
        _entry({"primary_factor_id": 7}), session=None, factor_cache=cache
    )
    assert result is factor


@pytest.mark.asyncio
async def test_get_factor_without_primary_factor_id_returns_none() -> None:
    # No matched factor = a legitimate skip (no heating leaf), not an error.
    result = await _HANDLER.get_factor_for_resolve_emission_types(
        _entry({}), session=None, factor_cache={}
    )
    assert result is None


@pytest.mark.asyncio
async def test_get_factor_dangling_id_raises() -> None:
    # id present but resolves to no factor (dangling FK) = corruption → raise.
    with patch("app.modules.buildings.schemas.FactorService") as mock_fs_cls:
        mock_fs_cls.return_value = MagicMock(get=AsyncMock(return_value=None))
        with pytest.raises(ValueError, match="does not exist"):
            await _HANDLER.get_factor_for_resolve_emission_types(
                _entry({"primary_factor_id": 5}), session=MagicMock(), factor_cache=None
            )
