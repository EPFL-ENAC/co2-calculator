"""Unit tests for UnitTotalsService (orchestration layer, mocked repos)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import ModuleStatus
from app.services.unit_totals_service import UnitTotalsService


def _session_with_module_rows(*row_sets):
    """Session whose execute() yields one module-rows result per call."""
    session = MagicMock()
    results = []
    for rows in row_sets:
        result = MagicMock()
        result.all.return_value = rows
        results.append(result)
    session.execute = AsyncMock(side_effect=results)
    return session


_VALIDATED_ROWS = [
    (4, ModuleStatus.VALIDATED, {"total": 5000.0}),
    (2, ModuleStatus.IN_PROGRESS, {"total": 999.0}),
    (1, ModuleStatus.VALIDATED, {"total": 100.0, "total_fte": 120.0}),
]


# ======================================================================
# get_results_summary
# ======================================================================


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_structure(mock_report_repo_cls):
    """Returned dict has the expected top-level keys."""
    report = MagicMock(id=1, unit_id=10, year=2024)
    mock_report_repo_cls.return_value.get = AsyncMock(return_value=report)
    mock_report_repo_cls.return_value.get_by_unit_and_year = AsyncMock(
        return_value=None
    )
    service = UnitTotalsService(session=_session_with_module_rows(_VALIDATED_ROWS))

    result = await service.get_results_summary(1)

    assert "current_emissions" in result
    assert "current_fte" in result
    assert "prev_emissions" in result


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_no_previous_report(mock_report_repo_cls):
    """No previous year report → prev_emissions == {}."""
    report = MagicMock(id=1, unit_id=10, year=2024)
    mock_report_repo_cls.return_value.get = AsyncMock(return_value=report)
    mock_report_repo_cls.return_value.get_by_unit_and_year = AsyncMock(
        return_value=None
    )
    service = UnitTotalsService(session=_session_with_module_rows(_VALIDATED_ROWS))

    result = await service.get_results_summary(1)
    assert result["prev_emissions"] == {}


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_with_previous_report(mock_report_repo_cls):
    """Previous year report exists → prev_emissions from its module stats."""
    report = MagicMock(id=1, unit_id=10, year=2024)
    prev_report = MagicMock(id=2, unit_id=10, year=2023)
    mock_report_repo_cls.return_value.get = AsyncMock(return_value=report)
    mock_report_repo_cls.return_value.get_by_unit_and_year = AsyncMock(
        return_value=prev_report
    )
    prev_rows = [(4, ModuleStatus.VALIDATED, {"total": 3000.0})]
    service = UnitTotalsService(
        session=_session_with_module_rows(_VALIDATED_ROWS, prev_rows)
    )

    result = await service.get_results_summary(1)
    assert result["prev_emissions"] == {"4": 3000.0}


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_report_not_found(mock_report_repo_cls):
    """CarbonReport not found → raises ValueError."""
    mock_report_repo_cls.return_value.get = AsyncMock(return_value=None)
    service = UnitTotalsService(session=MagicMock())

    with pytest.raises(ValueError, match="not found"):
        await service.get_results_summary(999)


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_non_validated_excluded(mock_report_repo_cls):
    """IN_PROGRESS modules are filtered; headcount FTE rides current_fte."""
    report = MagicMock(id=1, unit_id=10, year=2024)
    mock_report_repo_cls.return_value.get = AsyncMock(return_value=report)
    mock_report_repo_cls.return_value.get_by_unit_and_year = AsyncMock(
        return_value=None
    )
    service = UnitTotalsService(session=_session_with_module_rows(_VALIDATED_ROWS))

    result = await service.get_results_summary(1)
    assert "2" not in result["current_emissions"]  # travel (IN_PROGRESS) absent
    assert result["current_emissions"] == {"4": 5000.0, "1": 100.0}
    assert result["current_fte"] == {"1": 120.0}


# ======================================================================
# get_validated_emissions_by_unit
# ======================================================================


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.DataEntryEmissionRepository")
async def test_validated_emissions_basic(mock_emission_repo_cls):
    """Returns format [{"year": ..., "kg_co2eq": ...}]."""
    mock_emission_repo_cls.return_value.get_validated_totals_by_unit = AsyncMock(
        return_value=[{"year": 2023, "kg_co2eq": 61700.0}]
    )

    service = UnitTotalsService(session=MagicMock())
    result = await service.get_validated_emissions_by_unit(unit_id=1)
    assert result == [{"year": 2023, "kg_co2eq": 61700.0}]


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.DataEntryEmissionRepository")
async def test_validated_emissions_empty(mock_emission_repo_cls):
    """No data → empty list."""
    mock_emission_repo_cls.return_value.get_validated_totals_by_unit = AsyncMock(
        return_value=[]
    )

    service = UnitTotalsService(session=MagicMock())
    result = await service.get_validated_emissions_by_unit(unit_id=1)
    assert result == []
