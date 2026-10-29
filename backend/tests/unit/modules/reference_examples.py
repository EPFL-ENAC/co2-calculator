"""Harness for the #2771 reference-example tests.

Runs one worked example from the back-office doc (data-description.md,
"test calculation" boxes) through the production computation path:
``resolve_emission_types`` → ``handler.resolve_computations`` →
``DataEntryEmissionService._apply_formula``, summed over the entry's leaves.

``pre_compute`` reads the DB, so callers put its outputs (distance_km,
room_surface_square_meter, …) in ``ctx`` next to the entry data. Factor
values are copied from the INPUT_DATA CSVs, which CI does not have.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions.registry import resolve_emission_types
from app.modules.emissions.taxonomy import FactorLike
from app.schemas.data_entry import BaseModuleHandler
from app.services.data_entry_emission_service import DataEntryEmissionService

# The doc gives expected values to two decimals.
TOLERANCE_KG = 0.01


def compute_kg_co2eq(
    handler: BaseModuleHandler,
    data_entry_type: DataEntryTypeEnum,
    ctx: dict,
    factor_values: dict,
    *,
    factor: FactorLike | None = None,
) -> float:
    emission_types = resolve_emission_types(data_entry_type, ctx, factor=factor)
    assert emission_types, f"{data_entry_type.name} resolved to no leaf: {ctx}"
    # The cloud and purchase formulas need a year; rates are patched per test.
    full_ctx = {**ctx, "primary_factor_id": 1, "_year": 2025}
    data_entry = SimpleNamespace(id=None, data=ctx)
    service = DataEntryEmissionService(MagicMock())
    return sum(
        service._apply_formula(full_ctx, factor_values, comp)
        for emission_type in emission_types
        for comp in handler.resolve_computations(data_entry, emission_type, full_ctx)
    )
