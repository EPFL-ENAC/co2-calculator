"""#1236 Phase 4A.1 — in-pipeline aggregation coalesce gate.

``_is_last_recalc_sibling`` returns True only for the last
``emission_recalc`` sibling of a pipeline. Earlier siblings stamp
``meta.recalc_work_complete=True`` and return False so they skip the
aggregation chain; the final sibling returns True and chains a single
trailing aggregation (replacing today's 3× sequential aggregations).

Tests run on the SQLite ``db_session`` fixture; the helper accepts
the fixture session via its ``helper_session`` kwarg.
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
from app.tasks.emission_recalculation_tasks import _is_last_recalc_sibling


def _parent(*, pipeline_id, recalc_jobs_chained: int | None) -> DataIngestionJob:
    meta: dict = {}
    if recalc_jobs_chained is not None:
        meta["recalc_jobs_chained"] = recalc_jobs_chained
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=4,
        year=2026,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=False,
        pipeline_id=pipeline_id,
        job_type="csv_ingest",
        meta=meta,
    )


def _recalc(
    *, pipeline_id, parent_id: int, data_entry_type_id: int = 10
) -> DataIngestionJob:
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=4,
        data_entry_type_id=data_entry_type_id,
        year=2026,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        provider=UserProvider.DEFAULT,
        state=IngestionState.RUNNING,
        result=None,
        is_current=False,
        pipeline_id=pipeline_id,
        job_type="emission_recalc",
        meta={"parent_job_id": parent_id},
    )


@pytest.mark.asyncio
async def test_single_recalc_pipeline_is_last(db_session: AsyncSession):
    """expected=1, this is the only recalc → it IS the last sibling."""
    pid = uuid4()
    parent = _parent(pipeline_id=pid, recalc_jobs_chained=1)
    db_session.add(parent)
    await db_session.flush()
    recalc = _recalc(pipeline_id=pid, parent_id=parent.id)
    db_session.add(recalc)
    await db_session.flush()

    is_last = await _is_last_recalc_sibling(recalc, helper_session=db_session)

    assert is_last is True


@pytest.mark.asyncio
async def test_first_of_three_is_not_last(db_session: AsyncSession):
    """expected=3, only this one's recalc_work_complete set → not last."""
    pid = uuid4()
    parent = _parent(pipeline_id=pid, recalc_jobs_chained=3)
    db_session.add(parent)
    await db_session.flush()
    r1 = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=10)
    r2 = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=11)
    r3 = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=12)
    for r in (r1, r2, r3):
        db_session.add(r)
    await db_session.flush()

    is_last = await _is_last_recalc_sibling(r1, helper_session=db_session)

    assert is_last is False
    # r1's row now carries the flag (visible for r2/r3 next calls).
    await db_session.refresh(r1)
    assert (r1.meta or {}).get("recalc_work_complete") is True


@pytest.mark.asyncio
async def test_third_of_three_is_last(db_session: AsyncSession):
    """After r1 and r2 ran their gate (flag stamped), r3's gate → last."""
    pid = uuid4()
    parent = _parent(pipeline_id=pid, recalc_jobs_chained=3)
    db_session.add(parent)
    await db_session.flush()
    r1 = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=10)
    r2 = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=11)
    r3 = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=12)
    for r in (r1, r2, r3):
        db_session.add(r)
    await db_session.flush()

    # Simulate the first two siblings calling the gate in order.
    assert await _is_last_recalc_sibling(r1, helper_session=db_session) is False
    assert await _is_last_recalc_sibling(r2, helper_session=db_session) is False
    is_last = await _is_last_recalc_sibling(r3, helper_session=db_session)

    assert is_last is True


@pytest.mark.asyncio
async def test_legacy_no_pipeline_id_falls_back_to_true(
    db_session: AsyncSession,
):
    """No pipeline_id → preserves prior behavior (always chain)."""
    parent = _parent(pipeline_id=None, recalc_jobs_chained=1)
    db_session.add(parent)
    await db_session.flush()
    recalc = _recalc(pipeline_id=None, parent_id=parent.id)
    db_session.add(recalc)
    await db_session.flush()

    assert await _is_last_recalc_sibling(recalc, helper_session=db_session) is True


@pytest.mark.asyncio
async def test_legacy_no_recalc_jobs_chained_falls_back_to_true(
    db_session: AsyncSession,
):
    """Parent without ``recalc_jobs_chained`` meta → fall back to chain."""
    pid = uuid4()
    parent = _parent(pipeline_id=pid, recalc_jobs_chained=None)
    db_session.add(parent)
    await db_session.flush()
    recalc = _recalc(pipeline_id=pid, parent_id=parent.id)
    db_session.add(recalc)
    await db_session.flush()

    assert await _is_last_recalc_sibling(recalc, helper_session=db_session) is True


@pytest.mark.asyncio
async def test_legacy_no_parent_job_id_falls_back_to_true(
    db_session: AsyncSession,
):
    """Recalc without ``parent_job_id`` in meta → fall back to chain."""
    pid = uuid4()
    parent = _parent(pipeline_id=pid, recalc_jobs_chained=1)
    db_session.add(parent)
    await db_session.flush()
    recalc = _recalc(pipeline_id=pid, parent_id=parent.id)
    recalc.meta = {}  # strip parent_job_id
    db_session.add(recalc)
    await db_session.flush()

    assert await _is_last_recalc_sibling(recalc, helper_session=db_session) is True


# ---------------------------------------------------------------------------
# 4A.4 — _build_aggregation_scope_config
# ---------------------------------------------------------------------------

from app.tasks.emission_recalculation_tasks import (  # noqa: E402
    _build_aggregation_scope_config,
)


@pytest.mark.asyncio
async def test_scope_config_unions_own_and_siblings(db_session: AsyncSession):
    """Last sibling's own affected_module_ids (from local stats) + siblings'
    finished contributions → full union in the aggregation config."""
    pid = uuid4()
    parent = _parent(pipeline_id=pid, recalc_jobs_chained=3)
    db_session.add(parent)
    await db_session.flush()
    # Two FINISHED siblings with their affected_module_ids recorded.
    sibling_a = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=10)
    sibling_a.state = IngestionState.FINISHED
    sibling_a.meta = {
        **(sibling_a.meta or {}),
        "recalculation": {"affected_module_ids": [101, 202]},
    }
    sibling_b = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=11)
    sibling_b.state = IngestionState.FINISHED
    sibling_b.meta = {
        **(sibling_b.meta or {}),
        "recalculation": {"affected_module_ids": [202, 303]},
    }
    me = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=12)
    db_session.add_all([sibling_a, sibling_b, me])
    await db_session.flush()

    cfg = await _build_aggregation_scope_config(
        me, my_affected_module_ids=[303, 404], helper_session=db_session
    )

    assert cfg is not None
    assert cfg["affected_module_ids"] == [101, 202, 303, 404]


@pytest.mark.asyncio
async def test_scope_config_returns_empty_list_when_all_empty(
    db_session: AsyncSession,
):
    """Siblings exist but all reported empty affected; own also empty →
    returns {"affected_module_ids": []} (precise 'nothing to do', NOT
    the legacy fallback)."""
    pid = uuid4()
    parent = _parent(pipeline_id=pid, recalc_jobs_chained=2)
    db_session.add(parent)
    await db_session.flush()
    sib = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=10)
    sib.state = IngestionState.FINISHED
    sib.meta = {**(sib.meta or {}), "recalculation": {"affected_module_ids": []}}
    me = _recalc(pipeline_id=pid, parent_id=parent.id, data_entry_type_id=11)
    db_session.add_all([sib, me])
    await db_session.flush()

    cfg = await _build_aggregation_scope_config(
        me, my_affected_module_ids=[], helper_session=db_session
    )

    assert cfg == {"affected_module_ids": []}


@pytest.mark.asyncio
async def test_scope_config_returns_none_when_no_info(db_session: AsyncSession):
    """No siblings, no own ids, no pipeline_id → returns None so the
    aggregation falls back to the full slice (legacy behavior)."""
    me = _recalc(pipeline_id=None, parent_id=1, data_entry_type_id=10)
    me.meta = {}  # no parent_job_id either
    db_session.add(me)
    await db_session.flush()

    cfg = await _build_aggregation_scope_config(
        me, my_affected_module_ids=[], helper_session=db_session
    )

    assert cfg is None


@pytest.mark.asyncio
async def test_scope_config_uses_only_own_when_no_real_pipeline(
    db_session: AsyncSession,
):
    """Mock-style pipeline_id (not a real UUID) → helper short-circuits
    using just the caller's local affected_module_ids. Keeps mock-driven
    unit tests off the real SessionLocal path in production code."""
    # Simulate a non-UUID pipeline_id (e.g., test mock).
    me = _recalc(pipeline_id=None, parent_id=1)  # pipeline_id=None → same code path
    db_session.add(me)
    await db_session.flush()

    cfg = await _build_aggregation_scope_config(
        me, my_affected_module_ids=[7, 8, 9], helper_session=db_session
    )

    assert cfg == {"affected_module_ids": [7, 8, 9]}
