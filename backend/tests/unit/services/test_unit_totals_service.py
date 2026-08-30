"""Unit tests for UnitTotalsService (orchestration layer, mocked repos)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReportType
from app.services.unit_totals_service import UnitTotalsService

CALC = CarbonReportType.CALCULATOR

# ``module_stats_by_report`` rows: (report_id, module_type_id, status, stats, type)
_VALIDATED_ROWS = [
    (1, 1, ModuleStatus.VALIDATED, {"total": 100.0, "total_fte": 120.0}, CALC),
    (1, 2, ModuleStatus.IN_PROGRESS, {"total": 999.0}, CALC),
    (1, 4, ModuleStatus.VALIDATED, {"total": 5000.0}, CALC),
]


def _repo(mock_repo_cls, *, report=None, prev_report=None, rows=(), by_units=()):
    """Wire the patched CarbonReportRepository with the reads the service makes."""
    repo = mock_repo_cls.return_value
    repo.get = AsyncMock(return_value=report)
    repo.get_by_unit_and_year = AsyncMock(return_value=prev_report)
    repo.list_by_units = AsyncMock(return_value=list(by_units))
    repo.module_stats_by_report = AsyncMock(return_value=list(rows))
    return repo


# ======================================================================
# get_results_summary
# ======================================================================


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_structure(mock_report_repo_cls):
    """Returned dict has the expected top-level keys."""
    _repo(
        mock_report_repo_cls,
        report=MagicMock(id=1, unit_id=10, year=2024),
        rows=_VALIDATED_ROWS,
    )
    service = UnitTotalsService(session=MagicMock())

    result = await service.get_results_summary(1)

    assert "current_emissions" in result
    assert "current_fte" in result
    assert "prev_emissions" in result


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_no_previous_report(mock_report_repo_cls):
    """No previous year report → prev_emissions == {}."""
    _repo(
        mock_report_repo_cls,
        report=MagicMock(id=1, unit_id=10, year=2024),
        rows=_VALIDATED_ROWS,
    )
    service = UnitTotalsService(session=MagicMock())

    result = await service.get_results_summary(1)
    assert result["prev_emissions"] == {}


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_with_previous_report(mock_report_repo_cls):
    """Previous year report exists → prev_emissions from its module stats."""
    _repo(
        mock_report_repo_cls,
        report=MagicMock(id=1, unit_id=10, year=2024),
        prev_report=MagicMock(id=2, unit_id=10, year=2023),
        rows=[
            *_VALIDATED_ROWS,
            (2, 4, ModuleStatus.VALIDATED, {"total": 3000.0}, CALC),
        ],
    )
    service = UnitTotalsService(session=MagicMock())

    result = await service.get_results_summary(1)
    assert result["prev_emissions"] == {"4": 3000.0}


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_reads_both_years_in_one_query(mock_report_repo_cls):
    """Current and previous year module rows come back from a single read."""
    repo = _repo(
        mock_report_repo_cls,
        report=MagicMock(id=1, unit_id=10, year=2024),
        prev_report=MagicMock(id=2, unit_id=10, year=2023),
        rows=_VALIDATED_ROWS,
    )
    service = UnitTotalsService(session=MagicMock())

    await service.get_results_summary(1)

    repo.module_stats_by_report.assert_awaited_once_with([1, 2])


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_report_not_found(mock_report_repo_cls):
    """CarbonReport not found → raises ValueError."""
    _repo(mock_report_repo_cls, report=None)
    service = UnitTotalsService(session=MagicMock())

    with pytest.raises(ValueError, match="not found"):
        await service.get_results_summary(999)


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_non_validated_excluded(mock_report_repo_cls):
    """IN_PROGRESS modules are filtered; headcount FTE rides current_fte."""
    _repo(
        mock_report_repo_cls,
        report=MagicMock(id=1, unit_id=10, year=2024),
        rows=_VALIDATED_ROWS,
    )
    service = UnitTotalsService(session=MagicMock())

    result = await service.get_results_summary(1)
    assert "2" not in result["current_emissions"]  # travel (IN_PROGRESS) absent
    assert result["current_emissions"] == {"1": 100.0, "4": 5000.0}
    assert result["current_fte"] == {"1": 120.0}


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_results_summary_keeps_zero_total_validated_module(mock_report_repo_cls):
    """A validated module summing to 0.0 keeps its key — it is a real row.

    ``compute_results_summary`` turns this key set into the per-module rows of
    the response, so dropping the zero would silently shrink the payload.
    """
    _repo(
        mock_report_repo_cls,
        report=MagicMock(id=1, unit_id=10, year=2024),
        rows=[(1, 6, ModuleStatus.VALIDATED, {"total": 0.0}, CALC)],
    )
    service = UnitTotalsService(session=MagicMock())

    result = await service.get_results_summary(1)
    assert result["current_emissions"] == {"6": 0.0}


# ======================================================================
# get_merged_results_summary
# ======================================================================


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_merged_results_summary_is_constant_in_report_count(
    mock_report_repo_cls,
):
    """Three reports cost the same two reads as one (#2527 task 4)."""
    reports = [MagicMock(id=i, unit_id=i * 10, year=2024) for i in (1, 2, 3)]
    repo = _repo(
        mock_report_repo_cls,
        rows=[
            (r.id, 4, ModuleStatus.VALIDATED, {"total": 1000.0}, CALC) for r in reports
        ],
        by_units=[MagicMock(id=9, unit_id=10, year=2023)],
    )
    service = UnitTotalsService(session=MagicMock())

    result = await service.get_merged_results_summary(reports, 2024)

    assert repo.list_by_units.await_count == 1
    assert repo.module_stats_by_report.await_count == 1
    assert result["current_emissions"] == {"4": 3000.0}


@pytest.mark.asyncio
@patch("app.services.unit_totals_service.CarbonReportRepository")
async def test_merged_results_summary_splits_previous_year(mock_report_repo_cls):
    """Rows of the previous year's reports land in prev_emissions only."""
    reports = [MagicMock(id=1, unit_id=10, year=2024)]
    _repo(
        mock_report_repo_cls,
        rows=[
            (1, 4, ModuleStatus.VALIDATED, {"total": 5000.0}, CALC),
            (7, 4, ModuleStatus.VALIDATED, {"total": 3000.0}, CALC),
        ],
        by_units=[MagicMock(id=7, unit_id=10, year=2023)],
    )
    service = UnitTotalsService(session=MagicMock())

    result = await service.get_merged_results_summary(reports, 2024)

    assert result["current_emissions"] == {"4": 5000.0}
    assert result["prev_emissions"] == {"4": 3000.0}


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
