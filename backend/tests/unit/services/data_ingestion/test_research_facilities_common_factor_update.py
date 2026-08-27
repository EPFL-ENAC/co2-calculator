"""Tests for ResearchFacilitiesCommonFactorUpdateProvider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import IngestionResult
from app.modules.emissions import EmissionType
from app.services.data_ingestion.computed_providers.research_facilities_common import (
    ResearchFacilitiesCommonFactorUpdateProvider,
)
from app.tasks.ingestion_tasks import finalize_ingest_meta


def _make_provider() -> ResearchFacilitiesCommonFactorUpdateProvider:
    return ResearchFacilitiesCommonFactorUpdateProvider(
        config={}, data_session=MagicMock()
    )


def _make_factor(
    researchfacility_id: str | None, kg_co2eq_sum: float | None = None
) -> MagicMock:
    factor = MagicMock()
    factor.id = 42
    factor.classification = (
        {"researchfacility_id": researchfacility_id}
        if researchfacility_id is not None
        else {}
    )
    factor.values = {"kg_co2eq_sum": kg_co2eq_sum} if kg_co2eq_sum is not None else {}
    return factor


def _make_unit(unit_id: int = 1, is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(id=unit_id, is_active=is_active)


def _make_carbon_report(
    report_id: int = 10, stats: dict | None = None
) -> SimpleNamespace:
    return SimpleNamespace(id=report_id, stats=stats)


@pytest.mark.asyncio
async def test_happy_path_sums_all_valid_emissions():
    """Multiple leaf emission rows from different modules
    → kg_co2eq_sum = sum of all emissions of interest. Non-leaf rollup
    entries and research-facility leaves are excluded.
    """
    provider = _make_provider()
    factor = _make_factor("RF-001", None)
    session = MagicMock()

    breakdown = [
        (EmissionType.process_emissions__co2.value, 500.0),
        (EmissionType.buildings__combustion__natural_gas.value, 300.0),
        (EmissionType.equipment__it.value, 200.0),
        # Rollup entry: must not double-count on top of its leaves.
        (EmissionType.equipment.value, 200.0),
        # Research facility leaf: not included in the sum.
        (EmissionType.research_facilities__facilities.value, 600.0),
    ]

    with (
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.UnitRepository"
        ) as MockUnitRepo,
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.CarbonReportRepository"
        ) as MockCRRepo,
    ):
        MockUnitRepo.return_value.get_by_institutional_id = AsyncMock(
            return_value=_make_unit(1)
        )
        MockCRRepo.return_value.get_by_unit_and_year = AsyncMock(
            return_value=_make_carbon_report(
                10, {"by_emission_type": {str(id): amount for id, amount in breakdown}}
            )
        )

        result = await provider.compute_factor_values(factor, 2025, session)

    assert result == {"kg_co2eq_sum": 1000.0}


@pytest.mark.asyncio
async def test_unit_not_found_raises_value_error():
    """Unit not found → ValueError raised."""
    provider = _make_provider()
    factor = _make_factor("RF-MISSING")
    session = MagicMock()

    with patch(
        "app.services.data_ingestion.computed_providers.research_facilities_common.UnitRepository"
    ) as MockUnitRepo:
        MockUnitRepo.return_value.get_by_institutional_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Unit not found"):
            await provider.compute_factor_values(factor, 2025, session)


@pytest.mark.asyncio
async def test_carbon_report_not_found_raises_value_error():
    """CarbonReport not found → ValueError raised."""
    provider = _make_provider()
    factor = _make_factor("RF-001", None)
    session = MagicMock()

    with (
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.UnitRepository"
        ) as MockUnitRepo,
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.CarbonReportRepository"
        ) as MockCRRepo,
    ):
        MockUnitRepo.return_value.get_by_institutional_id = AsyncMock(
            return_value=_make_unit(1)
        )
        MockCRRepo.return_value.get_by_unit_and_year = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="CarbonReport not found"):
            await provider.compute_factor_values(factor, 2025, session)


@pytest.mark.asyncio
async def test_closed_unit_with_no_carbon_report_returns_zero_sum():
    """A closed unit (is_active=False) with no CarbonReport for the year is
    the expected case, not a gap — it stopped reporting, so 0.0 is the
    correct total, not an error.

    Regression: dev incident, factor for CLIMACT-GE (a closed unit) never
    got a kg_co2eq_sum, so every research-facilities entry against it
    422'd forever — the recompute had no report to sum from and raised
    instead of writing the (correct) zero.
    """
    provider = _make_provider()
    factor = _make_factor("RF-CLOSED", None)
    session = MagicMock()

    with (
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.UnitRepository"
        ) as MockUnitRepo,
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.CarbonReportRepository"
        ) as MockCRRepo,
    ):
        MockUnitRepo.return_value.get_by_institutional_id = AsyncMock(
            return_value=_make_unit(1, is_active=False)
        )
        MockCRRepo.return_value.get_by_unit_and_year = AsyncMock(return_value=None)

        result = await provider.compute_factor_values(factor, 2025, session)

    assert result == {"kg_co2eq_sum": 0.0}


@pytest.mark.asyncio
async def test_zero_emissions_returns_zero_sum():
    """Empty emission breakdown → returns {"kg_co2eq_sum": 0.0}."""
    provider = _make_provider()
    factor = _make_factor("RF-002", None)
    session = MagicMock()

    with (
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.UnitRepository"
        ) as MockUnitRepo,
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.CarbonReportRepository"
        ) as MockCRRepo,
    ):
        MockUnitRepo.return_value.get_by_institutional_id = AsyncMock(
            return_value=_make_unit(1)
        )
        MockCRRepo.return_value.get_by_unit_and_year = AsyncMock(
            return_value=_make_carbon_report(10)
        )

        result = await provider.compute_factor_values(factor, 2025, session)

    assert result == {"kg_co2eq_sum": 0.0}


@pytest.mark.asyncio
async def test_missing_researchfacility_id_returns_none():
    """Missing researchfacility_id in classification → returns None (factor skipped)."""
    provider = _make_provider()
    factor = _make_factor(None, None)
    session = MagicMock()

    result = await provider.compute_factor_values(factor, 2025, session)

    assert result is None


@pytest.mark.asyncio
async def test_existing_kg_co2eq_sum_skips_computation():
    """Existing kg_co2eq_sum in factor.values → returns None (factor skipped)."""
    provider = _make_provider()
    factor = _make_factor("RF-003", kg_co2eq_sum=123.45)
    session = MagicMock()

    result = await provider.compute_factor_values(factor, 2025, session)

    assert result is None


@pytest.mark.asyncio
async def test_ingest_captures_error_details_and_survives_finalize_ingest_meta():
    """Issue #1591 — a per-factor ``ValueError`` (e.g. an unmapped
    ``researchfacility_id``) must land in ``stats.error_details`` with the
    failing factor's id + message, and that detail must still be present,
    byte-for-byte, after ``finalize_ingest_meta`` flattens the provider's
    ``ingest()`` return into the handler meta that ``runner.py`` persists
    onto the job row (``metadata = dict(meta)`` — see ``run_job``).
    """
    provider = ResearchFacilitiesCommonFactorUpdateProvider(
        config={
            "data_entry_type_id": DataEntryTypeEnum.research_facilities.value,
            "year": 2025,
        },
        data_session=MagicMock(),
    )

    ok_factor = _make_factor("RF-OK", None)
    ok_factor.id = 1
    bad_factor = _make_factor("RF-MISSING", None)
    bad_factor.id = 2

    async def _get_by_institutional_id(researchfacility_id: str):
        return _make_unit(1) if researchfacility_id == "RF-OK" else None

    with (
        patch(
            "app.services.data_ingestion.factor_update_provider.FactorRepository"
        ) as MockFactorRepo,
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.UnitRepository"
        ) as MockUnitRepo,
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.CarbonReportRepository"
        ) as MockCRRepo,
    ):
        MockFactorRepo.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[ok_factor, bad_factor]
        )
        MockFactorRepo.return_value.update = AsyncMock()
        MockUnitRepo.return_value.get_by_institutional_id = AsyncMock(
            side_effect=_get_by_institutional_id
        )
        MockCRRepo.return_value.get_by_unit_and_year = AsyncMock(
            return_value=_make_carbon_report(10, {"by_emission_type": {}})
        )

        result = await provider.ingest()

    stats = result["data"]["stats"]
    assert stats["errors"] == 1
    assert stats["error_details"] == [
        {
            "factor_id": 2,
            "error": "Unit not found for researchfacility_id='RF-MISSING'",
        }
    ]
    assert result["data"]["result"] == IngestionResult.WARNING
    assert result["status_message"] == "Completed with 1 error(s)"

    meta = finalize_ingest_meta(result)

    # error_details must survive the flatten unchanged — this is exactly
    # what ends up in ``metadata = dict(meta)`` in ``runner.py``, which
    # ``finish_job`` then merges straight into the persisted job row's
    # ``meta`` JSON column.
    assert meta["stats"]["error_details"] == stats["error_details"]
    assert meta["result"] == IngestionResult.WARNING
