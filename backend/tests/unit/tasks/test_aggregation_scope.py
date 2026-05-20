"""#1236 Phase 4A.3 — ``_collect_affected_module_ids`` helper.

Uses the SQLite ``db_session`` fixture to seed real ``emission_recalc``
sibling rows with ``meta.recalculation.affected_module_ids`` and assert
the union the helper returns. Pairs with the MagicMock-driven
handler-scope tests in ``test_aggregation_handler.py``.
"""

from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider
from app.tasks.aggregation_tasks import _collect_affected_module_ids


def _recalc(
    *,
    pipeline_id,
    state: IngestionState = IngestionState.FINISHED,
    affected: list[int] | None = None,
    data_entry_type_id: int = 10,
) -> DataIngestionJob:
    meta: dict = {}
    if affected is not None:
        meta["recalculation"] = {"affected_module_ids": affected}
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=4,
        data_entry_type_id=data_entry_type_id,
        year=2026,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        provider=UserProvider.DEFAULT,
        state=state,
        result=IngestionResult.SUCCESS,
        is_current=False,
        pipeline_id=pipeline_id,
        job_type="emission_recalc",
        meta=meta,
    )


@pytest.mark.asyncio
async def test_returns_union_of_finished_sibling_affected_ids(
    db_session: AsyncSession,
):
    """3 FINISHED recalc siblings with disjoint+overlapping affected sets →
    helper returns the precise union (used to scope the aggregation)."""
    pid = uuid4()
    for r in (
        _recalc(pipeline_id=pid, affected=[101, 202], data_entry_type_id=10),
        _recalc(pipeline_id=pid, affected=[202, 303], data_entry_type_id=11),
        _recalc(pipeline_id=pid, affected=[303, 404], data_entry_type_id=12),
    ):
        db_session.add(r)
    await db_session.flush()

    result = await _collect_affected_module_ids(pid, db_session)

    assert result == {101, 202, 303, 404}


@pytest.mark.asyncio
async def test_ignores_non_finished_siblings(db_session: AsyncSession):
    """RUNNING / NOT_STARTED siblings don't contribute — only FINISHED
    counts (Phase 4A.1 coalesce guarantees the aggregation runs after
    every sibling is FINISHED, so this is the right snapshot)."""
    pid = uuid4()
    db_session.add(
        _recalc(
            pipeline_id=pid,
            state=IngestionState.FINISHED,
            affected=[1, 2],
            data_entry_type_id=10,
        )
    )
    db_session.add(
        _recalc(
            pipeline_id=pid,
            state=IngestionState.RUNNING,
            affected=[99],
            data_entry_type_id=11,
        )
    )
    await db_session.flush()

    result = await _collect_affected_module_ids(pid, db_session)

    assert result == {1, 2}


@pytest.mark.asyncio
async def test_returns_none_when_no_pipeline_id(db_session: AsyncSession):
    """No pipeline_id → legacy/orphan path; helper returns None so the
    caller falls back to the full (module, year) module list."""
    result = await _collect_affected_module_ids(None, db_session)
    assert result is None


@pytest.mark.asyncio
async def test_returns_none_when_no_affected_meta(db_session: AsyncSession):
    """Recalc siblings exist but none carry affected_module_ids →
    helper returns None (full-slice fallback). Common on legacy rows
    or before recalc started recording the field."""
    pid = uuid4()
    db_session.add(_recalc(pipeline_id=pid, affected=None, data_entry_type_id=10))
    db_session.add(_recalc(pipeline_id=pid, affected=None, data_entry_type_id=11))
    await db_session.flush()

    result = await _collect_affected_module_ids(pid, db_session)

    assert result is None


@pytest.mark.asyncio
async def test_returns_empty_set_when_recalcs_touched_nothing(
    db_session: AsyncSession,
):
    """Recalc siblings report empty affected_module_ids → helper returns
    an *empty* set (not None), so the aggregation correctly recomputes
    zero modules instead of falling back to the full slice."""
    pid = uuid4()
    db_session.add(_recalc(pipeline_id=pid, affected=[], data_entry_type_id=10))
    await db_session.flush()

    result = await _collect_affected_module_ids(pid, db_session)

    assert result == set()
