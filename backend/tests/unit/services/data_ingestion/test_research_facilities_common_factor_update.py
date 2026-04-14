"""Tests for ResearchFacilitiesCommonFactorUpdateProvider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_ingestion.computed_providers.research_facilities_common import (
    ResearchFacilitiesCommonFactorUpdateProvider,
)


def _make_provider() -> ResearchFacilitiesCommonFactorUpdateProvider:
    return ResearchFacilitiesCommonFactorUpdateProvider(
        config={}, data_session=MagicMock()
    )


def _make_factor(researchfacility_id: str | None) -> MagicMock:
    factor = MagicMock()
    factor.id = 42
    factor.classification = (
        {"researchfacility_id": researchfacility_id}
        if researchfacility_id is not None
        else {}
    )
    return factor


def _make_unit(unit_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(id=unit_id)


def _make_carbon_report(report_id: int = 10) -> SimpleNamespace:
    return SimpleNamespace(id=report_id)


@pytest.mark.asyncio
async def test_happy_path_sums_all_emissions():
    """Multiple emission rows from different modules → kg_co2eq_sum = sum of all."""
    provider = _make_provider()
    factor = _make_factor("RF-001")
    session = MagicMock()

    breakdown = [
        (1, 100, 500.0),
        (2, 200, 300.0),
        (3, 300, 200.0),
    ]

    with (
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.UnitRepository"
        ) as MockUnitRepo,
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.CarbonReportRepository"
        ) as MockCRRepo,
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.DataEntryEmissionRepository"
        ) as MockDEERepo,
    ):
        MockUnitRepo.return_value.get_by_institutional_id = AsyncMock(
            return_value=_make_unit(1)
        )
        MockCRRepo.return_value.get_by_unit_and_year = AsyncMock(
            return_value=_make_carbon_report(10)
        )
        MockDEERepo.return_value.get_emission_breakdown = AsyncMock(
            return_value=breakdown
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
    factor = _make_factor("RF-001")
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
async def test_zero_emissions_returns_zero_sum():
    """Empty emission breakdown → returns {"kg_co2eq_sum": 0.0}."""
    provider = _make_provider()
    factor = _make_factor("RF-002")
    session = MagicMock()

    with (
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.UnitRepository"
        ) as MockUnitRepo,
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.CarbonReportRepository"
        ) as MockCRRepo,
        patch(
            "app.services.data_ingestion.computed_providers.research_facilities_common.DataEntryEmissionRepository"
        ) as MockDEERepo,
    ):
        MockUnitRepo.return_value.get_by_institutional_id = AsyncMock(
            return_value=_make_unit(1)
        )
        MockCRRepo.return_value.get_by_unit_and_year = AsyncMock(
            return_value=_make_carbon_report(10)
        )
        MockDEERepo.return_value.get_emission_breakdown = AsyncMock(return_value=[])

        result = await provider.compute_factor_values(factor, 2025, session)

    assert result == {"kg_co2eq_sum": 0.0}


@pytest.mark.asyncio
async def test_missing_researchfacility_id_returns_none():
    """Missing researchfacility_id in classification → returns None (factor skipped)."""
    provider = _make_provider()
    factor = _make_factor(None)
    session = MagicMock()

    result = await provider.compute_factor_values(factor, 2025, session)

    assert result is None
