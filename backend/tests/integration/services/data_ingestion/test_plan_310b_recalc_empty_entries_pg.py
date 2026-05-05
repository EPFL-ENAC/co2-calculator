"""Plan 310B: emission_recalc must finish (FINISHED+SUCCESS) when there
are zero matching DataEntry rows.

Production failure observed by user: factors.csv uploaded for
data_entry_type_id=40 (external_clouds) with NO data_entries in the DB
left the recalc job stuck in ``state=RUNNING`` with no result and
``locked_by`` still set.  The expected behaviour is a graceful
"nothing to do" → FINISHED + SUCCESS, so the partial unique index
allows the next factor reupload to claim a fresh recalc job.

Two tests, both against real Postgres:

- ``test_workflow_returns_zeros_with_no_entries`` — direct call to
  ``EmissionRecalculationWorkflow.recalculate_for_data_entry_type``;
  the workflow itself must not raise on an empty entries list.
- ``test_run_recalculation_task_finishes_when_no_entries`` — the full
  task path: claim_job → workflow → final state.  Asserts the row
  lands FINISHED+SUCCESS on a separate engine (cross-connection).

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import ModuleTypeEnum
from app.models.user import UserProvider
from app.tasks.emission_recalculation_tasks import run_recalculation_task
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow


def _pending_recalc_job() -> DataIngestionJob:
    """Mirrors what _enqueue_stale_recalculations would create for an
    external_clouds (det=40) factor reupload."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=ModuleTypeEnum.external_cloud_and_ai.value,
        data_entry_type_id=DataEntryTypeEnum.external_clouds.value,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        provider=UserProvider.DEFAULT,
        state=IngestionState.NOT_STARTED,
        is_current=False,
        job_type="emission_recalc",
        meta={
            "config": {
                "year": 2025,
                "data_entry_type_id": DataEntryTypeEnum.external_clouds.value,
                "module_type_id": ModuleTypeEnum.external_cloud_and_ai.value,
                "parent_job_id": None,
            }
        },
    )


@pytest.mark.asyncio
async def test_workflow_returns_zeros_with_no_entries(pg_dsn):
    """The workflow itself must not raise when there are no DataEntry
    rows for the (det, year) slice — it returns zeroed stats."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as session:
        wf = EmissionRecalculationWorkflow(session)
        stats = await wf.recalculate_for_data_entry_type(
            DataEntryTypeEnum.external_clouds, 2025
        )

    await engine.dispose()

    assert stats == {
        "recalculated": 0,
        "modules_refreshed": 0,
        "errors": 0,
        "error_details": [],
    }


@pytest.mark.asyncio
async def test_run_recalculation_task_finishes_when_no_entries(pg_dsn, monkeypatch):
    """The full task path must transition the job to FINISHED+SUCCESS
    when there are no matching entries — not leave it stuck in RUNNING.

    Production observation: a factor reupload for det=40 with no
    data_entries left the recalc job in RUNNING with no result, blocking
    the next reupload from claiming.
    """
    # The task uses ``app.db.SessionLocal`` for both job and data sessions.
    # Point it at the test container.
    test_engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.tasks.emission_recalculation_tasks.SessionLocal", Sf)

    # Seed the recalc job in NOT_STARTED so the task can claim it.
    seed_engine = create_async_engine(pg_dsn, future=True)
    SeedSf = async_sessionmaker(
        seed_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SeedSf() as s:
        job = _pending_recalc_job()
        s.add(job)
        await s.commit()
        assert job.id is not None
        job_id: int = job.id
    await seed_engine.dispose()

    await run_recalculation_task(
        module_type_id=ModuleTypeEnum.external_cloud_and_ai.value,
        data_entry_type_id=DataEntryTypeEnum.external_clouds.value,
        year=2025,
        job_id=job_id,
    )

    # Verify on a separate engine — the row must be visible cross-
    # connection in the terminal state.
    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            row = (
                await vs.execute(
                    select(DataIngestionJob).where(col(DataIngestionJob.id) == job_id)
                )
            ).scalar_one()
    finally:
        await verify_engine.dispose()
        await test_engine.dispose()

    assert row.state == IngestionState.FINISHED, (
        f"Job stuck in {row.state} after no-entries recalc — production saw "
        "this as a job that never released its lock"
    )
    assert row.result == IngestionResult.SUCCESS, (
        f"Expected SUCCESS for empty-entries recalc, got result={row.result}"
    )
    # The lock should remain set (Plan 310A doesn't clear locked_by on
    # finish) but the state transition is what unblocks the next reupload's
    # claim — claim_job's Step 1 demotes ``is_current`` for siblings that
    # are NOT RUNNING, then Step 2 atomically claims the new candidate.
    assert row.locked_by is not None
    assert row.attempts == 1
