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
    entry.data = {}  # primary_factor_id is read from / written to entry.data
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
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
        patch(
            "app.workflows.emission_recalculation.ModuleHandlerService"
        ) as mock_handler_svc_cls,
    ):
        mock_handler_cls.get_by_type.return_value = MagicMock()
        mock_handler_svc_cls.return_value.resolve_primary_factor_id = AsyncMock(
            return_value={}
        )
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
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
        patch(
            "app.workflows.emission_recalculation.ModuleHandlerService"
        ) as mock_handler_svc_cls,
    ):
        mock_handler_cls.get_by_type.return_value = MagicMock()
        mock_handler_svc_cls.return_value.resolve_primary_factor_id = AsyncMock(
            return_value={}
        )
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
        patch("app.workflows.emission_recalculation.BaseModuleHandler"),
        patch("app.workflows.emission_recalculation.ModuleHandlerService"),
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
async def test_recalculate_rematches_primary_factor_id_when_changed():
    """Plan 310B Part 6: Strategy A entries (kind_field present in
    ``entry.data``) get their primary_factor_id refreshed when
    resolve_primary_factor_id returns a different id, before the
    emission recompute runs.
    """
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entry = _make_mock_entry(1, 10)
    # Strategy A shape: kind_field's value is present on entry.data,
    # so the rematch gate (``handler.kind_field in entry.data``) passes.
    entry.data = {"primary_factor_id": 999, "equipment_class": "Laptop"}

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
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
        patch(
            "app.workflows.emission_recalculation.ModuleHandlerService"
        ) as mock_handler_svc_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
        mock_module_cls.return_value.recompute_stats = AsyncMock()
        # Strategy A handler: kind_field maps to a key in entry.data so
        # the gate ``handler.kind_field in entry.data`` evaluates True.
        strategy_a_handler = MagicMock()
        strategy_a_handler.kind_field = "equipment_class"
        mock_handler_cls.get_by_type.return_value = strategy_a_handler
        # New factor matches against current state — different id
        mock_handler_svc_cls.return_value.resolve_primary_factor_id = AsyncMock(
            return_value={"primary_factor_id": 1234}
        )

        result = await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)

    assert result["recalculated"] == 1
    assert entry.data["primary_factor_id"] == 1234


@pytest.mark.asyncio
async def test_recalculate_does_not_touch_entry_when_factor_unchanged():
    """When resolve_primary_factor_id returns the same id, entry.data is
    untouched (no churn).
    """
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entry = _make_mock_entry(1, 10)
    original_data = {"primary_factor_id": 7, "extra": "preserved"}
    entry.data = dict(original_data)

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
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
        patch(
            "app.workflows.emission_recalculation.ModuleHandlerService"
        ) as mock_handler_svc_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
        mock_module_cls.return_value.recompute_stats = AsyncMock()
        mock_handler_cls.get_by_type.return_value = MagicMock()
        mock_handler_svc_cls.return_value.resolve_primary_factor_id = AsyncMock(
            return_value={"primary_factor_id": 7}
        )

        await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.plane, 2025)

    assert entry.data == original_data


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
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
        patch(
            "app.workflows.emission_recalculation.ModuleHandlerService"
        ) as mock_handler_svc_cls,
    ):
        mock_handler_cls.get_by_type.return_value = MagicMock()
        mock_handler_svc_cls.return_value.resolve_primary_factor_id = AsyncMock(
            return_value={}
        )
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


@pytest.mark.asyncio
async def test_recalculate_skips_rematch_for_strategy_b_handlers():
    """Plan 310B Part 6 (Copilot follow-up): Strategy B handlers like
    professional_travel/plane have ``kind_field`` set but derive the
    kind value in ``pre_compute`` — it isn't on ``entry.data``.  Running
    ``resolve_primary_factor_id`` against an empty kind would either
    clear primary_factor_id or raise MultipleResultsFound.

    The gate ``handler.kind_field in entry.data`` short-circuits the
    refresh for these handlers; this test pins the contract.
    """
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entry = _make_mock_entry(1, 10)
    # Strategy B shape: kind_field is "kind" but it's NOT in entry.data
    # (would be derived in pre_compute).  Existing primary_factor_id
    # must NOT be touched.
    entry.data = {"primary_factor_id": 7, "from_location": "GVA"}

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
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
        patch(
            "app.workflows.emission_recalculation.ModuleHandlerService"
        ) as mock_handler_svc_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
        mock_module_cls.return_value.recompute_stats = AsyncMock()
        # Strategy B handler shape: kind_field set, but its value isn't
        # present in entry.data (would be derived via pre_compute).
        strategy_b_handler = MagicMock()
        strategy_b_handler.kind_field = "kind"  # NOT a key on entry.data
        mock_handler_cls.get_by_type.return_value = strategy_b_handler
        # If the gate fails and the rematch runs, this would be the
        # value swapped in.  We assert the rematch was NOT called.
        mock_handler_svc_cls.return_value.resolve_primary_factor_id = AsyncMock(
            return_value={"primary_factor_id": 9999}
        )

        result = await svc.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, 2025
        )

    # Refresh skipped: resolver never called, primary_factor_id untouched.
    mock_handler_svc_cls.return_value.resolve_primary_factor_id.assert_not_called()
    assert entry.data["primary_factor_id"] == 7
    assert result["recalculated"] == 1


@pytest.mark.asyncio
async def test_recalculate_rolls_back_entry_data_on_upsert_failure():
    """Plan 310B Part 6 (Copilot follow-up): if ``upsert_by_data_entry``
    raises mid-loop, the in-memory ``entry.data`` mutation must be
    rolled back so the outer ``data_session.commit()`` doesn't persist
    a stale primary_factor_id alongside an old emissions row.
    """
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entry = _make_mock_entry(1, 10)
    # Strategy A shape so the rematch fires.
    entry.data = {"primary_factor_id": 7, "equipment_class": "Laptop"}
    original_data = dict(entry.data)

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
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
        patch(
            "app.workflows.emission_recalculation.ModuleHandlerService"
        ) as mock_handler_svc_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        # The compute step raises — simulates a downstream failure between
        # the rematch swap and the emissions-row write.
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock(
            side_effect=RuntimeError("compute blew up")
        )
        mock_module_cls.return_value.recompute_stats = AsyncMock()
        strategy_a_handler = MagicMock()
        strategy_a_handler.kind_field = "equipment_class"
        mock_handler_cls.get_by_type.return_value = strategy_a_handler
        # Resolver returns a different id — rematch tentatively swaps
        # entry.data['primary_factor_id'] from 7 → 1234, then upsert fails.
        mock_handler_svc_cls.return_value.resolve_primary_factor_id = AsyncMock(
            return_value={"primary_factor_id": 1234}
        )

        result = await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)

    # Per-entry error counted — the workflow swallows per-entry exceptions
    # so a single bad row doesn't abort the rest of the batch.
    assert result["errors"] == 1
    assert result["recalculated"] == 0
    # Critical: entry.data was rolled back to its pre-rematch shape.
    # Without the rollback, primary_factor_id would persist as 1234
    # while data_entry_emissions still references 7 → silent corruption.
    assert entry.data == original_data, (
        "entry.data must be restored on per-entry failure"
    )
