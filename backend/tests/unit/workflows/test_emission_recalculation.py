"""Unit tests for EmissionRecalculationWorkflow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow


def _make_mock_entry(entry_id: int, module_id: int) -> MagicMock:
    """Build a minimal mock DataEntry."""
    entry = MagicMock()
    entry.id = entry_id
    entry.carbon_report_module_id = module_id
    entry.data_entry_type_id = DataEntryTypeEnum.plane
    return entry


# ======================================================================
# recalculate_for_data_entry_type Tests
# ======================================================================


@pytest.mark.asyncio
async def test_recalculate_all_success():
    """All entries recalculate successfully → errors=0, correct counts."""
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entries = [_make_mock_entry(1, 10), _make_mock_entry(2, 10)]
    mock_entry_response = MagicMock()

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch(
            "app.workflows.emission_recalculation.CarbonReportModuleService"
        ) as mock_module_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryResponse"
        ) as mock_response_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
        mock_module_cls.return_value.recompute_stats = AsyncMock()
        mock_response_cls.model_validate.return_value = mock_entry_response

        result = await svc.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, 2025
        )

    assert result["recalculated"] == 2
    assert result["errors"] == 0
    assert result["error_details"] == []
    assert result["modules_refreshed"] == 1  # both entries in module 10


@pytest.mark.asyncio
async def test_recalculate_partial_error():
    """One entry raises an exception → error accumulated, others continue."""
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entries = [
        _make_mock_entry(1, 10),  # will succeed
        _make_mock_entry(2, 11),  # will fail
    ]

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch(
            "app.workflows.emission_recalculation.CarbonReportModuleService"
        ) as mock_module_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryResponse"
        ) as mock_response_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )

        # model_validate returns a mock with .id matching the entry
        def _model_validate(entry):
            m = MagicMock()
            m.id = entry.id
            return m

        mock_response_cls.model_validate.side_effect = _model_validate

        async def _upsert(entry_response):
            if entry_response.id == 2:
                raise ValueError("factor not found")

        mock_emission_cls.return_value.upsert_by_data_entry = _upsert
        mock_module_cls.return_value.recompute_stats = AsyncMock()

        result = await svc.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, 2025
        )

    assert result["recalculated"] == 1
    assert result["errors"] == 1
    assert len(result["error_details"]) == 1
    assert result["error_details"][0]["data_entry_id"] == 2
    assert "factor not found" in result["error_details"][0]["error"]
    # Only module 10 was successfully processed
    assert result["modules_refreshed"] == 1


@pytest.mark.asyncio
async def test_recalculate_empty_result():
    """No data entries for the type/year → all counts are zero."""
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch("app.workflows.emission_recalculation.DataEntryEmissionService"),
        patch("app.workflows.emission_recalculation.CarbonReportModuleService"),
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[]
        )

        result = await svc.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, 2025
        )

    assert result["recalculated"] == 0
    assert result["errors"] == 0
    assert result["modules_refreshed"] == 0
    assert result["error_details"] == []


@pytest.mark.asyncio
async def test_recalculate_module_stats_called_once_per_module():
    """recompute_stats is called exactly once per distinct CarbonReportModule."""
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    # Three entries across two modules
    entries = [
        _make_mock_entry(1, 10),
        _make_mock_entry(2, 10),
        _make_mock_entry(3, 11),
    ]
    mock_entry_response = MagicMock()

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch(
            "app.workflows.emission_recalculation.CarbonReportModuleService"
        ) as mock_module_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryResponse"
        ) as mock_response_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
        mock_module_cls.return_value.recompute_stats = AsyncMock()
        mock_response_cls.model_validate.return_value = mock_entry_response

        result = await svc.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, 2025
        )

    assert result["recalculated"] == 3
    assert result["modules_refreshed"] == 2
    assert mock_module_cls.return_value.recompute_stats.await_count == 2
