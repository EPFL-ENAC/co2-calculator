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
            "app.workflows.emission_recalculation.FactorRepository"
        ) as mock_factor_repo_cls,
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
        mock_handler_cls.get_by_type.return_value = MagicMock()
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        mock_factor_repo_cls.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[]
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
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
            "app.workflows.emission_recalculation.FactorRepository"
        ) as mock_factor_repo_cls,
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
        mock_handler_cls.get_by_type.return_value = MagicMock()
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        mock_factor_repo_cls.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[]
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
            "app.workflows.emission_recalculation.FactorRepository"
        ) as mock_factor_repo_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        # Bulk dict has the new factor for kind=Laptop with id=1234.
        new_factor = MagicMock()
        new_factor.id = 1234
        new_factor.classification = {"equipment_class": "Laptop"}
        mock_factor_repo_cls.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[new_factor]
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
        # Strategy A handler: kind_field maps to a key in entry.data so
        # the gate ``handler.kind_field in entry.data`` evaluates True.
        strategy_a_handler = MagicMock()
        strategy_a_handler.kind_field = "equipment_class"
        strategy_a_handler.subkind_field = None
        mock_handler_cls.get_by_type.return_value = strategy_a_handler

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
            "app.workflows.emission_recalculation.FactorRepository"
        ) as mock_factor_repo_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        mock_factor_repo_cls.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[]
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
        # Handler with no kind_field (MagicMock attr is not in entry.data
        # so the rematch gate fails) — entry.data stays untouched.
        mock_handler_cls.get_by_type.return_value = MagicMock()

        await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.plane, 2025)

    assert entry.data == original_data


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
            "app.workflows.emission_recalculation.FactorRepository"
        ) as mock_factor_repo_cls,
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
        mock_handler_cls.get_by_type.return_value = MagicMock()
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        mock_factor_repo_cls.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[]
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
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
            "app.workflows.emission_recalculation.FactorRepository"
        ) as mock_factor_repo_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        mock_factor_repo_cls.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[]
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
        # Strategy B handler shape: kind_field set, but its value isn't
        # present in entry.data (would be derived via pre_compute).
        strategy_b_handler = MagicMock()
        strategy_b_handler.kind_field = "kind"  # NOT a key on entry.data
        strategy_b_handler.subkind_field = None
        mock_handler_cls.get_by_type.return_value = strategy_b_handler

        result = await svc.recalculate_for_data_entry_type(
            DataEntryTypeEnum.plane, 2025
        )

    # Refresh skipped: primary_factor_id untouched.  (The per-entry DB
    # resolver fallback was removed in Plan 310-D's strict-drop refactor;
    # the gate above is now the only thing keeping Strategy B safe.)
    assert entry.data["primary_factor_id"] == 7
    assert result["recalculated"] == 1
    # Plan 310D Copilot follow-up: the bulk-prefetch SELECT must also be
    # skipped for Strategy B slices.  Without this gate every Strategy B
    # recalc paid for an extra ``list_by_data_entry_type`` query that
    # was guaranteed to feed zero useful lookups.
    mock_factor_repo_cls.return_value.list_by_data_entry_type.assert_not_called()


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
            "app.workflows.emission_recalculation.FactorRepository"
        ) as mock_factor_repo_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        # Bulk dict has the new factor with id 1234 — rematch tentatively
        # swaps entry.data['primary_factor_id'] from 7 → 1234, then upsert
        # fails so the rollback restores the original.
        new_factor = MagicMock()
        new_factor.id = 1234
        new_factor.classification = {"equipment_class": "Laptop"}
        mock_factor_repo_cls.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[new_factor]
        )
        # The compute step raises — simulates a downstream failure between
        # the rematch swap and the emissions-row write.
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock(
            side_effect=RuntimeError("compute blew up")
        )
        strategy_a_handler = MagicMock()
        strategy_a_handler.kind_field = "equipment_class"
        strategy_a_handler.subkind_field = None
        mock_handler_cls.get_by_type.return_value = strategy_a_handler

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


@pytest.mark.asyncio
async def test_recalculate_uses_single_factor_bulk_fetch():
    """Plan 310D: the workflow pulls all factors for
    ``(data_entry_type_id, year)`` in a SINGLE call before the per-entry
    loop, then resolves ``primary_factor_id`` via Python dict lookup.

    Three Strategy A entries:
    - Two share kind ``Laptop`` → both hit the bulk dict.
    - One has kind ``Server`` not in the bulk dict → strict-drop:
      ``primary_factor_id`` is cleared to ``None`` (no DB fallback).

    Asserts:
    - ``factor_repo.list_by_data_entry_type`` is called EXACTLY ONCE.
    - Dict-hit entries get the bulk-loaded factor id.
    - Dict-miss entry has ``primary_factor_id`` cleared to ``None``.
    """
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    laptop_a = _make_mock_entry(1, 10)
    laptop_a.data = {"primary_factor_id": 0, "equipment_class": "Laptop"}
    laptop_b = _make_mock_entry(2, 10)
    laptop_b.data = {"primary_factor_id": 0, "equipment_class": "Laptop"}
    server = _make_mock_entry(3, 10)
    server.data = {"primary_factor_id": 0, "equipment_class": "Server"}
    entries = [laptop_a, laptop_b, server]

    # Bulk-loaded factor: matches kind=Laptop only.
    laptop_factor = MagicMock()
    laptop_factor.id = 4242
    laptop_factor.classification = {"equipment_class": "Laptop"}

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.FactorRepository"
        ) as mock_factor_repo_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=entries
        )
        mock_factor_repo_cls.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[laptop_factor]
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
        strategy_a_handler = MagicMock()
        strategy_a_handler.kind_field = "equipment_class"
        strategy_a_handler.subkind_field = None
        mock_handler_cls.get_by_type.return_value = strategy_a_handler

        await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)

    # Single bulk SELECT, regardless of entry count.
    bulk_call = mock_factor_repo_cls.return_value.list_by_data_entry_type
    assert bulk_call.await_count == 1

    # Bulk-hit entries linked to the bulk factor; miss has its
    # primary_factor_id cleared to None (strict-drop, Plan 310-D).
    assert laptop_a.data["primary_factor_id"] == 4242
    assert laptop_b.data["primary_factor_id"] == 4242
    assert server.data["primary_factor_id"] is None


@pytest.mark.asyncio
async def test_recalculate_kind_only_fallback_in_dict():
    """Plan 310-D Copilot follow-up: in-memory kind→subkind→kind-only fallback.

    When an entry has a non-empty subkind but the current factor set has
    only a kind-only row (subkind=NULL), the in-memory dict lookup must
    fall through ``(kind, None)`` rather than missing and clearing the
    factor link.  This used to cost a per-entry DB roundtrip via the
    resolver fallback; now it's an O(1) dict lookup.
    """
    mock_session = MagicMock()
    svc = EmissionRecalculationWorkflow(mock_session)

    # Entry asks for (Laptop, Premium); current factors only have
    # (Laptop, NULL) — kind-only fallback should hit it.
    entry = _make_mock_entry(1, 10)
    entry.data = {
        "primary_factor_id": 0,
        "equipment_class": "Laptop",
        "sub_class": "Premium",
    }
    kind_only_factor = MagicMock()
    kind_only_factor.id = 555
    # No sub_class → registers as (Laptop, None) in the bulk dict.
    kind_only_factor.classification = {"equipment_class": "Laptop"}

    with (
        patch(
            "app.workflows.emission_recalculation.DataEntryRepository"
        ) as mock_repo_cls,
        patch(
            "app.workflows.emission_recalculation.FactorRepository"
        ) as mock_factor_repo_cls,
        patch(
            "app.workflows.emission_recalculation.DataEntryEmissionService"
        ) as mock_emission_cls,
        patch("app.workflows.emission_recalculation.DataEntryResponse"),
        patch(
            "app.workflows.emission_recalculation.BaseModuleHandler"
        ) as mock_handler_cls,
    ):
        mock_repo_cls.return_value.list_by_data_entry_type_and_year = AsyncMock(
            return_value=[entry]
        )
        mock_factor_repo_cls.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[kind_only_factor]
        )
        mock_emission_cls.return_value.upsert_by_data_entry = AsyncMock()
        handler = MagicMock()
        handler.kind_field = "equipment_class"
        handler.subkind_field = "sub_class"
        mock_handler_cls.get_by_type.return_value = handler

        await svc.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)

    # Kind-only fallback hit — primary_factor_id resolved to 555 from
    # the (Laptop, None) bulk-dict entry, NOT cleared and NOT a DB call.
    assert entry.data["primary_factor_id"] == 555
