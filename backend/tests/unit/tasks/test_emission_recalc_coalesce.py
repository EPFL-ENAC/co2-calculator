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
    Pipeline,
    PipelineStatus,
    TargetType,
)
from app.models.user import UserProvider
from app.tasks.emission_recalculation_tasks import _is_last_recalc_sibling


async def _seed_pipeline(
    session: AsyncSession, *, pipeline_id, expected_recalc: int | None
) -> None:
    """Phase 5B (#1236) — coalesce gate reads ``expected`` from
    ``pipelines.expected_recalc``, not ``parent.meta.recalc_jobs_chained``.
    Tests seed both the Pipeline row and the parent job so the gate has
    its full read environment.
    """
    if pipeline_id is None:
        return
    session.add(
        Pipeline(
            id=pipeline_id,
            kind="csv_ingest",
            status=PipelineStatus.RUNNING.value,
            expected_recalc=expected_recalc,
        )
    )
    await session.flush()


def _parent(*, pipeline_id) -> DataIngestionJob:
    """Parent ingest job — Phase 5B: no ``recalc_jobs_chained`` meta
    (it's on ``pipelines.expected_recalc`` now)."""
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
        meta={},
    )


def _recalc(*, pipeline_id, data_entry_type_id: int = 10) -> DataIngestionJob:
    """Recalc child — Phase 5B: no ``parent_job_id`` meta (root is
    identifiable by lowest-id job in the pipeline)."""
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
        meta={},
    )


@pytest.mark.asyncio
async def test_single_recalc_pipeline_is_last(db_session: AsyncSession):
    """expected=1, this is the only recalc → it IS the last sibling."""
    pid = uuid4()
    await _seed_pipeline(db_session, pipeline_id=pid, expected_recalc=1)
    db_session.add(_parent(pipeline_id=pid))
    recalc = _recalc(pipeline_id=pid)
    db_session.add(recalc)
    await db_session.flush()

    is_last = await _is_last_recalc_sibling(recalc, helper_session=db_session)

    assert is_last is True


@pytest.mark.asyncio
async def test_first_of_three_is_not_last(db_session: AsyncSession):
    """expected=3, only this one's recalc_work_complete set → not last."""
    pid = uuid4()
    await _seed_pipeline(db_session, pipeline_id=pid, expected_recalc=3)
    db_session.add(_parent(pipeline_id=pid))
    r1 = _recalc(pipeline_id=pid, data_entry_type_id=10)
    r2 = _recalc(pipeline_id=pid, data_entry_type_id=11)
    r3 = _recalc(pipeline_id=pid, data_entry_type_id=12)
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
    await _seed_pipeline(db_session, pipeline_id=pid, expected_recalc=3)
    db_session.add(_parent(pipeline_id=pid))
    r1 = _recalc(pipeline_id=pid, data_entry_type_id=10)
    r2 = _recalc(pipeline_id=pid, data_entry_type_id=11)
    r3 = _recalc(pipeline_id=pid, data_entry_type_id=12)
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
    parent = _parent(pipeline_id=None)
    db_session.add(parent)
    await db_session.flush()
    recalc = _recalc(pipeline_id=None)
    db_session.add(recalc)
    await db_session.flush()

    assert await _is_last_recalc_sibling(recalc, helper_session=db_session) is True


@pytest.mark.asyncio
async def test_legacy_pipeline_without_expected_recalc_falls_back_to_true(
    db_session: AsyncSession,
):
    """Pipeline row exists but ``expected_recalc`` is NULL (e.g. legacy
    pre-Phase-5A pipelines) → coalesce gate falls back to True so the
    aggregation chain still fires (preserves prior behavior)."""
    pid = uuid4()
    await _seed_pipeline(db_session, pipeline_id=pid, expected_recalc=None)
    db_session.add(_parent(pipeline_id=pid))
    recalc = _recalc(pipeline_id=pid)
    db_session.add(recalc)
    await db_session.flush()

    assert await _is_last_recalc_sibling(recalc, helper_session=db_session) is True


@pytest.mark.asyncio
async def test_legacy_no_pipeline_row_falls_back_to_true(
    db_session: AsyncSession,
):
    """Pipeline row missing entirely (pre-Phase-1 legacy / dropped row)
    → gate falls back to True so the aggregation chain still fires."""
    pid = uuid4()
    # NO _seed_pipeline call — Pipeline row absent.
    db_session.add(_parent(pipeline_id=pid))
    recalc = _recalc(pipeline_id=pid)
    db_session.add(recalc)
    await db_session.flush()

    assert await _is_last_recalc_sibling(recalc, helper_session=db_session) is True


@pytest.mark.asyncio
async def test_concurrent_siblings_yield_exactly_one_last(
    db_session: AsyncSession,
):
    """LOCK-DOWN test for 4A.1 (#1236 Phase 5B advisor blocker).

    Two siblings both call the gate against the SAME ``pipeline_id``.
    The lock moved from parent-job to pipeline row in Phase 5B; if the
    lock target moved wrong (e.g. lock on parent stayed while the read
    of ``expected_recalc`` migrated to pipelines), BOTH siblings could
    see "done >= expected" and chain their own aggregation — silently
    regressing the coalesce to N aggregations per pipeline.

    With correct serialisation, exactly one of the two returns True
    (the second caller, after the first stamped its own flag).
    """
    pid = uuid4()
    await _seed_pipeline(db_session, pipeline_id=pid, expected_recalc=2)
    db_session.add(_parent(pipeline_id=pid))
    r1 = _recalc(pipeline_id=pid, data_entry_type_id=10)
    r2 = _recalc(pipeline_id=pid, data_entry_type_id=11)
    db_session.add_all([r1, r2])
    await db_session.flush()

    # Sequential calls on the shared session (the production gate opens
    # its own short-lived session and SELECT … FOR UPDATEs the pipeline
    # row to serialise; here we exercise the predicate logic with the
    # injected helper_session so the order-independence assertion holds
    # via the recalc_work_complete flag — see test_third_of_three).
    a = await _is_last_recalc_sibling(r1, helper_session=db_session)
    b = await _is_last_recalc_sibling(r2, helper_session=db_session)

    assert (a, b).count(True) == 1, (
        f"Exactly ONE sibling must be 'last' — got {(a, b)} "
        "(if both True, 4A.1's single-aggregation guarantee is broken)"
    )


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
    await _seed_pipeline(db_session, pipeline_id=pid, expected_recalc=3)
    db_session.add(_parent(pipeline_id=pid))
    # Two FINISHED siblings with their affected_module_ids recorded.
    sibling_a = _recalc(pipeline_id=pid, data_entry_type_id=10)
    sibling_a.state = IngestionState.FINISHED
    sibling_a.meta = {
        **(sibling_a.meta or {}),
        "recalculation": {"affected_module_ids": [101, 202]},
    }
    sibling_b = _recalc(pipeline_id=pid, data_entry_type_id=11)
    sibling_b.state = IngestionState.FINISHED
    sibling_b.meta = {
        **(sibling_b.meta or {}),
        "recalculation": {"affected_module_ids": [202, 303]},
    }
    me = _recalc(pipeline_id=pid, data_entry_type_id=12)
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
    await _seed_pipeline(db_session, pipeline_id=pid, expected_recalc=2)
    db_session.add(_parent(pipeline_id=pid))
    sib = _recalc(pipeline_id=pid, data_entry_type_id=10)
    sib.state = IngestionState.FINISHED
    sib.meta = {**(sib.meta or {}), "recalculation": {"affected_module_ids": []}}
    me = _recalc(pipeline_id=pid, data_entry_type_id=11)
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
    me = _recalc(pipeline_id=None, data_entry_type_id=10)
    me.meta = {}
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
    me = _recalc(pipeline_id=None)  # pipeline_id=None → same code path
    db_session.add(me)
    await db_session.flush()

    cfg = await _build_aggregation_scope_config(
        me, my_affected_module_ids=[7, 8, 9], helper_session=db_session
    )

    assert cfg == {"affected_module_ids": [7, 8, 9]}
