"""Unit tests that the plane emission formula produces correct kg CO₂eq values.

Formula (from issue #863):
    kg_co2eq = distance_km × EF(category, cabin_class) × RFI_adjustment

EF / RFI values are taken directly from backend/seed_data/travel_planes_factors.csv.
No DB or async fixture is needed — ``_apply_formula`` is pure arithmetic.
"""

import pytest

from app.models.data_entry_emission import EmissionComputation
from app.modules.emissions import EmissionType
from app.modules.professional_travel import ProfessionalTravelPlaneModuleHandler
from app.services.data_entry_emission_service import DataEntryEmissionService

# ---------------------------------------------------------------------------
# Factor values from travel_planes_factors.csv (all RFI = 1.35)
# ---------------------------------------------------------------------------
_EF = {
    ("short_to_medium_haul", "economy"): 0.2906,
    ("short_to_medium_haul", "business"): 0.4471,
    ("medium_to_long_haul", "economy"): 0.1902,
    ("medium_to_long_haul", "business"): 0.3930,
}
_RFI = 1.35


def _svc() -> DataEntryEmissionService:
    """Service instance with no DB session — _apply_formula is pure."""
    return DataEntryEmissionService(None)  # type: ignore[arg-type]


def _comp() -> EmissionComputation:
    """Minimal EmissionComputation for plane handler resolve_computations."""
    return EmissionComputation(
        emission_type=EmissionType.professional_travel__plane__eco,
        formula_key="ef_kg_co2eq_per_km",
        quantity_key="distance_km",
        multiplier_key="rfi_adjustment",
        multiplier_default=1.0,
    )


# ---------------------------------------------------------------------------
# 1. Formula correctness for all 4 factor combinations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category, cabin_class, distance_km",
    [
        ("short_to_medium_haul", "economy", 506.0),  # GVA → CDG (haversine+95)
        ("short_to_medium_haul", "business", 506.0),
        ("medium_to_long_haul", "economy", 5926.0),  # CDG → JFK
        ("medium_to_long_haul", "business", 5926.0),
    ],
)
def test_apply_formula_matches_spec(
    category: str, cabin_class: str, distance_km: float
) -> None:
    ef = _EF[(category, cabin_class)]
    expected = distance_km * ef * _RFI

    result = _svc()._apply_formula(
        ctx={"distance_km": distance_km},
        factor_values={"ef_kg_co2eq_per_km": ef, "rfi_adjustment": _RFI},
        comp=_comp(),
    )

    assert result == pytest.approx(expected, rel=1e-6), (
        f"{category}/{cabin_class}: expected {expected:.4f} kg CO₂eq, got {result}"
    )


# ---------------------------------------------------------------------------
# 2. Short-haul economy formula at the reference distance
# ---------------------------------------------------------------------------


def test_short_haul_economy_formula() -> None:
    distance_km = 500.0
    ef = _EF[("short_to_medium_haul", "economy")]
    eco = _svc()._apply_formula(
        ctx={"distance_km": distance_km},
        factor_values={
            "ef_kg_co2eq_per_km": ef,
            "rfi_adjustment": _RFI,
        },
        comp=_comp(),
    )
    assert eco == pytest.approx(distance_km * ef * _RFI, rel=1e-9)


# ---------------------------------------------------------------------------
# 3. Business > economy on both hauls
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("category", ["short_to_medium_haul", "medium_to_long_haul"])
def test_business_emits_more_than_economy(category: str) -> None:
    distance_km = 1000.0
    eco = _svc()._apply_formula(
        ctx={"distance_km": distance_km},
        factor_values={
            "ef_kg_co2eq_per_km": _EF[(category, "economy")],
            "rfi_adjustment": _RFI,
        },
        comp=_comp(),
    )
    biz = _svc()._apply_formula(
        ctx={"distance_km": distance_km},
        factor_values={
            "ef_kg_co2eq_per_km": _EF[(category, "business")],
            "rfi_adjustment": _RFI,
        },
        comp=_comp(),
    )
    assert biz > eco, (
        f"{category}: business ({biz:.2f}) should exceed economy ({eco:.2f})"
    )


# ---------------------------------------------------------------------------
# 4. Long-haul business is the highest emitter per km
# ---------------------------------------------------------------------------


def test_long_haul_business_highest_emitter() -> None:
    distance_km = 6000.0
    results = {
        cls: _svc()._apply_formula(
            ctx={"distance_km": distance_km},
            factor_values={
                "ef_kg_co2eq_per_km": _EF[("medium_to_long_haul", cls)],
                "rfi_adjustment": _RFI,
            },
            comp=_comp(),
        )
        for cls in ("economy", "business")
    }
    assert results["business"] > results["economy"], (
        f"Long-haul ranking wrong: {results}"
    )


# ---------------------------------------------------------------------------
# 5. number_of_trips multiplier (distance_km already = one_trip × n_trips)
# ---------------------------------------------------------------------------


def test_two_trips_doubles_emission() -> None:
    distance_one_trip = 506.0
    ef = _EF[("short_to_medium_haul", "economy")]

    one = _svc()._apply_formula(
        ctx={"distance_km": distance_one_trip},
        factor_values={"ef_kg_co2eq_per_km": ef, "rfi_adjustment": _RFI},
        comp=_comp(),
    )
    two = _svc()._apply_formula(
        ctx={"distance_km": distance_one_trip * 2},
        factor_values={"ef_kg_co2eq_per_km": ef, "rfi_adjustment": _RFI},
        comp=_comp(),
    )
    assert two == pytest.approx(one * 2, rel=1e-9)


# ---------------------------------------------------------------------------
# 6. resolve_computations wires the correct FactorQuery keys
# ---------------------------------------------------------------------------


def test_resolve_computations_passes_cabin_class_as_subkind() -> None:
    """The handler must forward cabin_class as subkind so the factor repo
    can match the right EF row (category × cabin_class)."""
    handler = ProfessionalTravelPlaneModuleHandler()

    class _FakeEntry:
        id = 1
        data = {"cabin_class": "business"}

    ctx = {"haul_category": "short_to_medium_haul", "distance_km": 506.0}
    computations = handler.resolve_computations(
        _FakeEntry(), EmissionType.professional_travel__plane__business, ctx
    )

    assert len(computations) == 1
    fq = computations[0].factor_query
    assert fq is not None
    assert fq.kind == "short_to_medium_haul", (
        f"expected haul_category as kind, got {fq.kind}"
    )
    assert fq.subkind == "business", (
        f"expected cabin_class as subkind, got {fq.subkind}"
    )


@pytest.mark.parametrize("cabin_class", ["economy", "business"])
def test_resolve_computations_all_classes(cabin_class: str) -> None:
    handler = ProfessionalTravelPlaneModuleHandler()

    class _FakeEntry:
        id = 1
        data = {"cabin_class": cabin_class}

    ctx = {"haul_category": "medium_to_long_haul", "distance_km": 5926.0}
    computations = handler.resolve_computations(
        _FakeEntry(), EmissionType.professional_travel__plane__business, ctx
    )
    assert computations[0].factor_query.subkind == cabin_class
