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
    }
    assert _formula(_ctx(use=0.0), fv) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Share-based fallback (no kg_co2eq_sum_{source}, only {source}_share + kg_co2eq)
# ---------------------------------------------------------------------------


def test_share_based_fallback_is_weighted_by_entry_kg_co2eq() -> None:
    # shares sum to 1.0, entry kg_co2eq = 100 -> 100.0
    fv = {
        "use_unit": "kg",
        "total_use": 100.0,
        "processemissions_share": 0.5,
        "building_energycombustions_share": 0.2,
        "building_rooms_share": 0.1,
        "purchases_common_share": 0.1,
        "purchases_additional_share": 0.05,
        "equipments_share": 0.05,
    }
    assert _formula(_ctx(), fv) == pytest.approx(100.0)


def test_zero_share_contributes_zero_not_skipped() -> None:
    fv = {"use_unit": "kg", "total_use": 100.0, "processemissions_share": 0.0}
    assert _formula(_ctx(), fv) == pytest.approx(0.0)


def test_share_without_entry_kg_co2eq_is_skipped() -> None:
    # source_share present but kg_co2eq is None on the entry -> source contributes
    # nothing; with no other source contributing, overall result is None.
    fv = {"use_unit": "kg", "total_use": 100.0, "processemissions_share": 0.5}
    assert _formula(_ctx(kg_co2eq=None), fv) is None


# ---------------------------------------------------------------------------
# Mixed sources: some facility-specific, some share-based
# ---------------------------------------------------------------------------


def test_mixed_facility_specific_and_share_based_sources_sum_together() -> None:
    # processemissions uses its facility-specific sum (use_share=0.1 -> 5.0);
    # building_energycombustions has no sum, falls back to share*kg_co2eq (20.0);
    # remaining sources have neither a sum nor a share -> contribute nothing.
    fv = {
        "use_unit": "kg",
        "total_use": 100.0,
        "kg_co2eq_sum_processemissions": 50.0,
        "building_energycombustions_share": 0.2,
    }
    assert _formula(_ctx(), fv) == pytest.approx(25.0)


def test_no_source_contributes_returns_none() -> None:
    fv = {"use_unit": "kg", "total_use": 100.0}
    assert _formula(_ctx(), fv) is None


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


def test_zero_total_use_raises_zero_division_error() -> None:
    # Documents current behavior: total_use=0 is accepted by the factor's
    # validator (only negative values are rejected), but the formula divides
    # `use` by `total_use` unconditionally, so a zero total_use blows up here
    # rather than degrading to None.
    fv = {"use_unit": "kg", "total_use": 0.0, "kg_co2eq_sum_processemissions": 50.0}
    with pytest.raises(ZeroDivisionError):
        _formula(_ctx(), fv)
