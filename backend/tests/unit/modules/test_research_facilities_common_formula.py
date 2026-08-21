"""Unit tests for ResearchFacilitiesCommonModuleHandler._research_facilities_formula.

Formula: ``(use / total_use) * kg_co2eq_sum``, gated by a matching
``use_unit`` between entry and factor. The two entry-point guards
(``use``/``use_unit`` missing, unit mismatch, missing ``total_use``) all
short-circuit to ``None`` — those describe an incomplete entry or a
never-configured factor.

``kg_co2eq_sum`` is different: it's optional at factor creation, filled
later by ``ResearchFacilitiesCommonFactorUpdateProvider``'s computed
backfill. A factor still missing it isn't malformed, its backfill just
hasn't run — so that case raises a specific ``ValueError`` rather than
returning ``None`` (dev incident: a bare "could not produce a value"
500 for factor_id=37756 gave no clue which factor or why).

The formula is a closure defined inside ``resolve_computations``, reached
the same way callers reach it: via ``resolve_computations(...)
[0].formula_func``.
"""

import pytest

from app.modules.emissions import EmissionType
from app.modules.research_facilities import ResearchFacilitiesCommonModuleHandler

_HANDLER = ResearchFacilitiesCommonModuleHandler()


def _ctx(
    *,
    use: float | None = 10.0,
    use_unit: str | None = "kg",
) -> dict:
    return {"use": use, "use_unit": use_unit, "primary_factor_id": 1}


def _formula(ctx: dict, factor_values: dict) -> float | None:
    comps = _HANDLER.resolve_computations(
        None, EmissionType.research_facilities__facilities, ctx
    )
    assert len(comps) == 1
    return comps[0].formula_func(ctx, factor_values)


def test_resolve_computations_without_factor_id_returns_empty() -> None:
    ctx = {"use": 10.0, "use_unit": "kg"}
    assert (
        _HANDLER.resolve_computations(
            None, EmissionType.research_facilities__facilities, ctx
        )
        == []
    )


def test_computes_use_share_times_kg_co2eq_sum() -> None:
    fv = {"use_unit": "kg", "total_use": 100.0, "kg_co2eq_sum": 50.0}
    assert _formula(_ctx(use=10.0), fv) == pytest.approx(5.0)


@pytest.mark.parametrize(
    "ctx_kwargs",
    [
        pytest.param({"use": None}, id="missing-use"),
        pytest.param({"use_unit": None}, id="missing-use_unit"),
    ],
)
def test_missing_required_entry_fields_return_none(ctx_kwargs: dict) -> None:
    fv = {"use_unit": "kg", "total_use": 100.0, "kg_co2eq_sum": 50.0}
    assert _formula(_ctx(**ctx_kwargs), fv) is None


def test_unit_mismatch_between_entry_and_factor_returns_none() -> None:
    fv = {"use_unit": "lb", "total_use": 100.0, "kg_co2eq_sum": 50.0}
    assert _formula(_ctx(use_unit="kg"), fv) is None


def test_missing_total_use_returns_none() -> None:
    fv = {"use_unit": "kg", "kg_co2eq_sum": 50.0}
    assert _formula(_ctx(), fv) is None


def test_missing_kg_co2eq_sum_raises_value_error_naming_the_facility() -> None:
    # Regression: factor_id=37756 had {"total_use", "use_unit"} only —
    # kg_co2eq_sum's computed backfill never ran — and the entry create
    # 500'd with a bare "could not produce a value", no facility name.
    ctx = _ctx()
    ctx["researchfacility_name"] = "ISIC-ITDMP"
    fv = {"use_unit": "kg", "total_use": 100.0}
    with pytest.raises(ValueError, match="ISIC-ITDMP"):
        _formula(ctx, fv)


def test_missing_kg_co2eq_sum_error_defaults_facility_name_to_unknown() -> None:
    fv = {"use_unit": "kg", "total_use": 100.0}
    with pytest.raises(ValueError, match="Unknown"):
        _formula(_ctx(), fv)
