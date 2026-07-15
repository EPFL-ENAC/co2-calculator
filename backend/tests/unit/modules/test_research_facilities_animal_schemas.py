"""Unit tests for ResearchFacilitiesAnimalModuleHandler._research_facilities_formula.

Formula: for each of the six sources (processemissions, building_energycombustions,
building_rooms, purchases_common, purchases_additional, equipments):

  - if the factor carries a facility-specific ``kg_co2eq_sum_{source}``, add
    ``use_share * kg_co2eq_sum_{source}`` (use_share = use / total_use).
  - otherwise, if the factor carries a ``{source}_share`` and the entry carries
    a total ``kg_co2eq``, add ``{source}_share * kg_co2eq``.
  - otherwise the source contributes nothing.

The two entry-point guards (``use``/``use_unit`` missing, unit mismatch between
entry and factor, missing ``total_use``) all short-circuit to ``None``.

The formula is a closure defined inside ``resolve_computations``, so it is
reached the same way callers reach it: via ``resolve_computations(...)
[0].formula_func``.
"""

import pytest

from app.modules.emissions import EmissionType
from app.modules.research_facilities.animals_schemas import (
    ResearchFacilitiesAnimalModuleHandler,
)

_HANDLER = ResearchFacilitiesAnimalModuleHandler()


def _ctx(
    *,
    use: float | None = 10.0,
    use_unit: str | None = "kg",
    kg_co2eq: float | None = 100.0,
) -> dict:
    return {
        "use": use,
        "use_unit": use_unit,
        "kg_co2eq": kg_co2eq,
        "primary_factor_id": 1,
    }


def _formula(ctx: dict, factor_values: dict) -> float | None:
    comps = _HANDLER.resolve_computations(
        None, EmissionType.research_facilities__animal, ctx
    )
    assert len(comps) == 1
    return comps[0].formula_func(ctx, factor_values)


# ---------------------------------------------------------------------------
# resolve_computations gating
# ---------------------------------------------------------------------------


def test_resolve_computations_without_factor_id_returns_empty() -> None:
    ctx = {"use": 10.0, "use_unit": "kg"}
    assert (
        _HANDLER.resolve_computations(
            None, EmissionType.research_facilities__animal, ctx
        )
        == []
    )


# ---------------------------------------------------------------------------
# Facility-specific emissions (kg_co2eq_sum_{source} present)
# ---------------------------------------------------------------------------


def test_facility_specific_sums_are_weighted_by_use_share() -> None:
    # use_share = 10 / 100 = 0.1; sum of source sums = 100 -> 0.1 * 100 = 10.0
    fv = {
        "use_unit": "kg",
        "total_use": 100.0,
        "kg_co2eq_sum_processemissions": 50.0,
        "kg_co2eq_sum_building_energycombustions": 20.0,
        "kg_co2eq_sum_building_rooms": 0.0,
        "kg_co2eq_sum_purchases_common": 10.0,
        "kg_co2eq_sum_purchases_additional": 5.0,
        "kg_co2eq_sum_equipments": 15.0,
    }
    assert _formula(_ctx(), fv) == pytest.approx(10.0)


def test_zero_use_with_facility_specific_sum_yields_zero_not_none() -> None:
    fv = {
        "use_unit": "kg",
        "total_use": 100.0,
        "kg_co2eq_sum_processemissions": 50.0,
        "kg_co2eq_sum_building_energycombustions": 20.0,
        "kg_co2eq_sum_building_rooms": 0.0,
        "kg_co2eq_sum_purchases_common": 10.0,
        "kg_co2eq_sum_purchases_additional": 5.0,
        "kg_co2eq_sum_equipments": 15.0,
    }
    assert _formula(_ctx(use=0.0), fv) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Entry-point guards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ctx_kwargs",
    [
        pytest.param({"use": None}, id="missing-use"),
        pytest.param({"use_unit": None}, id="missing-use_unit"),
    ],
)
def test_missing_required_entry_fields_return_none(ctx_kwargs: dict) -> None:
    fv = {
        "use_unit": "kg",
        "total_use": 100.0,
        "kg_co2eq_sum_processemissions": 50.0,
    }
    assert _formula(_ctx(**ctx_kwargs), fv) is None


def test_unit_mismatch_between_entry_and_factor_returns_none() -> None:
    fv = {
        "use_unit": "lb",
        "total_use": 100.0,
        "kg_co2eq_sum_processemissions": 50.0,
    }
    assert _formula(_ctx(use_unit="kg"), fv) is None


def test_factor_missing_use_unit_is_treated_as_mismatch() -> None:
    fv = {"total_use": 100.0, "kg_co2eq_sum_processemissions": 50.0}
    assert _formula(_ctx(use_unit="kg"), fv) is None


def test_missing_total_use_returns_none() -> None:
    fv = {"use_unit": "kg", "kg_co2eq_sum_processemissions": 50.0}
    assert _formula(_ctx(), fv) is None


# ---------------------------------------------------------------------------
# Missing per-source kg_co2eq_sum in factor values
# ---------------------------------------------------------------------------


def test_missing_source_in_factor_values_raises_value_error() -> None:
    # kg_co2eq_sum_building_energycombustions (and the remaining sources) are
    # absent from factor_values, so the first missing source encountered
    # should raise instead of silently skipping.
    fv = {
        "use_unit": "kg",
        "total_use": 100.0,
        "kg_co2eq_sum_processemissions": 50.0,
    }
    with pytest.raises(
        ValueError,
        match="Missing kg_co2eq_sum for source building_energycombustions",
    ):
        _formula(_ctx(), fv)


def test_missing_source_error_includes_facility_name_and_type() -> None:
    ctx = _ctx()
    ctx["researchfacility_name"] = "Animal House"
    ctx["researchfacility_type"] = "rodent"
    fv = {"use_unit": "kg", "total_use": 100.0}
    with pytest.raises(ValueError, match=r"facility Animal House \(rodent\)"):
        _formula(ctx, fv)


def test_missing_source_error_defaults_facility_name_and_type_to_unknown() -> None:
    fv = {"use_unit": "kg", "total_use": 100.0}
    with pytest.raises(ValueError, match=r"facility Unknown \(Unknown\)"):
        _formula(_ctx(), fv)
