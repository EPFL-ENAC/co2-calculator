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
    entry.data = {}
    return entry


def _make_mock_handler() -> MagicMock:
    """Handler mock whose async ``prefetch_slice`` hook returns an empty
    slice cache — the workflow awaits it once before looping entries."""
    handler = MagicMock()
    handler.prefetch_slice = AsyncMock(return_value={})
    return handler


def _patch_resolver_empty(mock_resolver_cls) -> None:
    """Wire a FactorResolver mock whose bulk map is empty — the shape
    most tests need when the resolved factor id doesn't matter."""
    mock_resolver_cls.return_value.factors_by_id = AsyncMock(return_value={})


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
            "app.workflows.emission_recalculation.FactorResolver"
        ) as mock_resolver_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryResponse"
        ) as mock_response_cls,
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_handler_cls.get_by_type.return_value = _make_mock_handler()
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        _patch_resolver_empty(mock_resolver_cls)
        mock_emission_cls.return_value.prepare_create = AsyncMock(return_value=[])
        mock_emission_cls.return_value.bulk_replace_for_entries = AsyncMock(
            return_value=0
        )
        mock_response_cls.model_validate.return_value = mock_entry_response

        result = await svc.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, 2025
        )

    assert result["recalculated"] == 2
    assert result["errors"] == 0
    assert result["error_details"] == []
    # Plan 310-D: stats writer moved to the runner-driven aggregation
    # handler.  The workflow now reports the affected module ids so
    # the runner can chain aggregation; ``modules_refreshed`` is
    # retained for back-compat but always 0 from this layer.
    assert result["modules_refreshed"] == 0
    assert result["affected_module_ids"] == [10]


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
            "app.workflows.emission_recalculation.FactorResolver"
        ) as mock_resolver_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryResponse"
        ) as mock_response_cls,
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_handler_cls.get_by_type.return_value = _make_mock_handler()
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        _patch_resolver_empty(mock_resolver_cls)

        # model_validate returns a mock with .id matching the entry
        def _model_validate(entry):
            m = MagicMock()
            m.id = entry.id
            return m

        mock_response_cls.model_validate.side_effect = _model_validate

        async def _prepare(entry_response, **kwargs):
            if entry_response.id == 2:
                raise ValueError("factor not found")
            return []

        mock_emission_cls.return_value.prepare_create = _prepare
        mock_emission_cls.return_value.bulk_replace_for_entries = AsyncMock(
            return_value=0
        )

        result = await svc.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, 2025
        )

    assert result["recalculated"] == 1
    assert result["errors"] == 1
    assert len(result["error_details"]) == 1
    assert result["error_details"][0]["data_entry_id"] == 2
    assert "factor not found" in result["error_details"][0]["error"]
    # Only module 10's entry succeeded — the failed entry's module is
    # absent from ``affected_module_ids`` (the rollback drops it).
    # ``modules_refreshed`` is always 0 now (handler chains aggregation).
    assert result["modules_refreshed"] == 0
    assert result["affected_module_ids"] == [10]


@pytest.mark.asyncio
async def test_recalculate_aborts_batch_on_connection_invalidated():
    """A connection-invalidated DBAPIError aborts the whole batch
    (re-raised) instead of looping the same fatal error per remaining
    entry.  Regression for the stage incident where one dead-connection
    failure produced one identical "transaction aborted / can't
    reconnect" log line per remaining data_entry and a silently failed
    job.  Re-raising lets the runner record FINISHED+ERROR with the
    real cause (per-entry data errors still continue — see
    test_recalculate_partial_error)."""
    from sqlalchemy.exc import DBAPIError

    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entries = [_make_mock_entry(1, 10), _make_mock_entry(2, 11)]

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.FactorResolver"
        ) as mock_resolver_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryResponse"
        ) as mock_response_cls,
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_handler_cls.get_by_type.return_value = _make_mock_handler()
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        _patch_resolver_empty(mock_resolver_cls)

        def _model_validate(entry):
            m = MagicMock()
            m.id = entry.id
            return m

        mock_response_cls.model_validate.side_effect = _model_validate

        upsert_calls: list[int] = []

        async def _prepare(entry_response, **kwargs):
            upsert_calls.append(entry_response.id)
            if entry_response.id == 1:
                raise DBAPIError(
                    "UPDATE data_entry_emissions ...",
                    {},
                    Exception("server closed the connection unexpectedly"),
                    connection_invalidated=True,
                )
            return []

        mock_emission_cls.return_value.prepare_create = _prepare
        mock_emission_cls.return_value.bulk_replace_for_entries = AsyncMock(
            return_value=0
        )

        with pytest.raises(DBAPIError):
            await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.plane, 2025)

    # Aborted at the first entry — the second was never attempted, so
    # no error storm and no masking of the first cause.
    assert upsert_calls == [1]


@pytest.mark.asyncio
async def test_recalculate_aborts_batch_on_pending_rollback():
    """A ``PendingRollbackError`` / ``InvalidRequestError`` (the
    "Can't reconnect until invalid transaction is rolled back" shape
    actually seen in the stage storm) must also abort the batch — not
    just ``DBAPIError.connection_invalidated``.  This is the case the
    first version of the fix missed: once the session needs a full
    rollback, every remaining entry (including ``begin_nested()``'s
    SAVEPOINT enter) re-raises the same error."""
    from sqlalchemy.exc import PendingRollbackError

    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entries = [_make_mock_entry(1, 10), _make_mock_entry(2, 11)]

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.FactorResolver"
        ) as mock_resolver_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryResponse"
        ) as mock_response_cls,
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_handler_cls.get_by_type.return_value = _make_mock_handler()
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        _patch_resolver_empty(mock_resolver_cls)

        def _model_validate(entry):
            m = MagicMock()
            m.id = entry.id
            return m

        mock_response_cls.model_validate.side_effect = _model_validate

        upsert_calls: list[int] = []

        async def _prepare(entry_response, **kwargs):
            upsert_calls.append(entry_response.id)
            if entry_response.id == 1:
                raise PendingRollbackError(
                    "This Session's transaction has been rolled back "
                    "due to a previous exception during flush."
                )
            return []

        mock_emission_cls.return_value.prepare_create = _prepare
        mock_emission_cls.return_value.bulk_replace_for_entries = AsyncMock(
            return_value=0
        )

        with pytest.raises(PendingRollbackError):
            await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.plane, 2025)

    assert upsert_calls == [1]


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
        patch("app.workflows.emission_recalculation.BaseModuleHandler"),
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
    assert result["affected_module_ids"] == []
    assert result["error_details"] == []


@pytest.mark.asyncio
async def test_recalculate_reports_affected_module_ids_for_chain():
    """Plan 310-D — workflow no longer calls ``recompute_stats``;
    instead it reports ``affected_module_ids`` so the calling handler
    can chain a single deduplicated aggregation pass for the slice.
    Distinct module ids in ``affected_module_ids`` == "modules whose
    stats need refreshing once the recalc commits"."""
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
            "app.workflows.emission_recalculation.FactorResolver"
        ) as mock_resolver_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryResponse"
        ) as mock_response_cls,
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_handler_cls.get_by_type.return_value = _make_mock_handler()
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        _patch_resolver_empty(mock_resolver_cls)
        mock_emission_cls.return_value.prepare_create = AsyncMock(return_value=[])
        mock_emission_cls.return_value.bulk_replace_for_entries = AsyncMock(
            return_value=0
        )
        mock_response_cls.model_validate.return_value = mock_entry_response

        result = await svc.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, 2025
        )

    assert result["recalculated"] == 3
    # Plan 310-D: workflow doesn't call recompute_stats anymore; the
    # affected modules are reported up the chain so the handler can
    # fire a single aggregation pass per (module, year) slice.
    assert result["modules_refreshed"] == 0
    assert sorted(result["affected_module_ids"]) == [10, 11]


@pytest.mark.asyncio
async def test_recalculate_reports_progress_at_interval(monkeypatch):
    """Every PROGRESS_INTERVAL computed entries, the workflow logs and
    invokes the caller's progress callback (the handlers stamp it onto
    the job row so SSE/UI can track long recalcs)."""
    import app.workflows.emission_recalculation as wf_mod

    monkeypatch.setattr(wf_mod, "PROGRESS_INTERVAL", 1)
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entries = [_make_mock_entry(1, 10), _make_mock_entry(2, 10)]
    progress_calls: list[tuple[int, int]] = []

    async def _progress(done: int, total: int) -> None:
        progress_calls.append((done, total))

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.FactorResolver"
        ) as mock_resolver_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_handler_cls.get_by_type.return_value = _make_mock_handler()
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        _patch_resolver_empty(mock_resolver_cls)
        mock_emission_cls.return_value.prepare_create = AsyncMock(return_value=[])
        mock_emission_cls.return_value.bulk_replace_for_entries = AsyncMock(
            return_value=0
        )

        await svc.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, 2025, progress_callback=_progress
        )

    assert progress_calls == [(1, 2), (2, 2)]


# ======================================================================
# Primary factor resolution (plan 1661) — the recalc loop no longer
# rematches primary_factor_id itself; it builds ONE shared
# FactorResolver per slice and hands it to ``prepare_create``, which
# resolves the factor and stamps it onto the emission row.  The
# matching rules themselves (kind/subkind, override-key-first,
# strict-drop on miss) are FactorResolver's responsibility and are
# covered by tests/unit/services/test_factor_resolver.py.
# ======================================================================


@pytest.mark.asyncio
async def test_recalculate_never_mutates_entry_data():
    """entry.data is read-only input to the loop — no tentative swap,
    no rollback-on-failure. Assert identity AND value are unchanged."""
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entry = _make_mock_entry(1, 10)
    entry.data = {"primary_factor_id": 999, "equipment_class": "Laptop"}
    data_ref = entry.data
    original_data = dict(entry.data)

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.FactorResolver"
        ) as mock_resolver_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        strategy_a_handler = _make_mock_handler()
        strategy_a_handler.kind_field = "equipment_class"
        strategy_a_handler.subkind_field = None
        mock_handler_cls.get_by_type.return_value = strategy_a_handler
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        new_factor = MagicMock(id=1234)
        mock_resolver_cls.return_value.factors_by_id = AsyncMock(
            return_value={1234: new_factor}
        )
        mock_emission_cls.return_value.prepare_create = AsyncMock(return_value=[])
        mock_emission_cls.return_value.bulk_replace_for_entries = AsyncMock(
            return_value=0
        )

        result = await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)

    assert result["recalculated"] == 1
    assert entry.data is data_ref
    assert entry.data == original_data


@pytest.mark.asyncio
async def test_recalculate_entry_data_untouched_on_per_entry_failure():
    """A per-entry ``prepare_create`` failure has nothing to roll back —
    entry.data was never written to in the first place."""
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entry = _make_mock_entry(1, 10)
    entry.data = {"primary_factor_id": 7, "equipment_class": "Laptop"}
    original_data = dict(entry.data)

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.FactorResolver"
        ) as mock_resolver_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        strategy_a_handler = _make_mock_handler()
        strategy_a_handler.kind_field = "equipment_class"
        strategy_a_handler.subkind_field = None
        mock_handler_cls.get_by_type.return_value = strategy_a_handler
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        _patch_resolver_empty(mock_resolver_cls)
        mock_emission_cls.return_value.prepare_create = AsyncMock(
            side_effect=RuntimeError("compute blew up")
        )
        mock_emission_cls.return_value.bulk_replace_for_entries = AsyncMock(
            return_value=0
        )

        result = await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)

    assert result["errors"] == 1
    assert result["recalculated"] == 0
    assert entry.data == original_data


@pytest.mark.asyncio
async def test_recalculate_shares_one_resolver_across_entries():
    """The recalc loop builds ONE FactorResolver per slice and passes
    the SAME instance to every ``prepare_create`` call, so the
    resolver's memoized bulk SELECT (``factors_by_id``) runs once
    regardless of how many entries are in the slice — not once per
    entry."""
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entries = [
        _make_mock_entry(1, 10),
        _make_mock_entry(2, 10),
        _make_mock_entry(3, 10),
    ]

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.FactorResolver"
        ) as mock_resolver_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryResponse"
        ) as mock_response_cls,
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_handler_cls.get_by_type.return_value = _make_mock_handler()
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        _patch_resolver_empty(mock_resolver_cls)
        mock_response_cls.model_validate.return_value = MagicMock()

        seen_resolvers = []

        async def _prepare(entry_response, **kwargs):
            seen_resolvers.append(kwargs["factor_resolver"])
            return []

        mock_emission_cls.return_value.prepare_create = _prepare
        mock_emission_cls.return_value.bulk_replace_for_entries = AsyncMock(
            return_value=0
        )

        await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)

    assert mock_resolver_cls.call_count == 1
    mock_resolver_cls.return_value.factors_by_id.assert_awaited_once()
    assert len(seen_resolvers) == 3
    assert all(r is mock_resolver_cls.return_value for r in seen_resolvers)


@pytest.mark.asyncio
async def test_recalculate_carries_new_factor_id_into_emission_rows():
    """After a factor swap, the recalculated emission rows (buffered
    for ``bulk_replace_for_entries``) carry the new
    ``DataEntryEmission.primary_factor_id`` — the resolved id lives on
    the emission, never back on ``entry.data``."""
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    entry = _make_mock_entry(1, 10)
    entry.data = {"primary_factor_id": 999, "equipment_class": "Laptop"}
    original_data = dict(entry.data)
    new_factor_id = 1234

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.FactorResolver"
        ) as mock_resolver_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        strategy_a_handler = _make_mock_handler()
        strategy_a_handler.kind_field = "equipment_class"
        strategy_a_handler.subkind_field = None
        mock_handler_cls.get_by_type.return_value = strategy_a_handler
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        new_factor = MagicMock(id=new_factor_id)
        mock_resolver_cls.return_value.factors_by_id = AsyncMock(
            return_value={new_factor_id: new_factor}
        )

        async def _prepare(entry_response, **kwargs):
            # Stand-in for the real prepare_create (Task 2): it resolves
            # the primary factor via the shared resolver and stamps its
            # id onto the emission row.
            emission = MagicMock(primary_factor_id=new_factor_id)
            return [emission]

        mock_emission_cls.return_value.prepare_create = AsyncMock(side_effect=_prepare)
        bulk_replace = AsyncMock(return_value=1)
        mock_emission_cls.return_value.bulk_replace_for_entries = bulk_replace

        result = await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)

    assert result["recalculated"] == 1
    bulk_replace.assert_awaited_once()
    _entry_ids, emissions = bulk_replace.call_args.args
    assert emissions[0].primary_factor_id == new_factor_id
    # The resolved id landed on the emission row, not back on entry.data.
    assert entry.data == original_data
