"""Regression tests for ``POST /sync/pipelines/{pipeline_id}/abort``.

User-reported (Guilbert, 2026-05-21): the legacy ``POST /jobs/{id}/cancel``
returned 404 because clicking it after the pipeline-debug refactor
(#1236) hit the "single-job operation in a pipeline-shaped world" gap.
A typical chain has csv_ingest → emission_recalc(N) → aggregation, and
cancel could only target one link, leaving the rest orphaned.

Fix: cancel removed; replaced by ``abort_pipeline`` which marks every
non-terminal job of the pipeline ``FINISHED + ERROR`` AND clears
``locked_by`` so an in-flight handler's preemption check (see
``runner.py:270``) trips and rolls back its data writes.  Without
the lock clear, the handler would happily complete and overwrite
the abort marker with ``FINISHED + SUCCESS`` seconds later.

These tests pin:
1. The happy path (non-terminal jobs flip, terminal jobs untouched).
2. The 409 surface when nothing's left to abort.
3. The 404 surface for an unknown pipeline_id.
4. The cleared-lock contract — this is the load-bearing invariant the
   runner depends on; if it regresses the abort silently un-applies
   when the in-flight handler finishes.

Requires Docker — ``conftest.py``'s ``postgres_container``.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
import app.core.security as security_module
from app.main import app
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
from app.models.module_type import ModuleTypeEnum
from app.models.user import UserProvider

ABORT_URL_TEMPLATE = "/api/v1/sync/pipelines/{pipeline_id}/abort"
TEST_USER_EMAIL = "operator@test.example"
TEST_POD_ID = "test-pod-123"


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire FastAPI to test PG + bypass auth.

    Mirrors the auth + dependency-override rig used by the dispatch
    tests in this directory; no file storage / runner SessionLocal
    patches needed because the abort endpoint touches only the DB.
    """
    psycopg_dsn = pg_dsn.replace("+asyncpg", "+psycopg")
    test_engine = create_async_engine(psycopg_dsn, future=True)
    Sf = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = TEST_USER_EMAIL
    fake_user.institutional_id = "TEST-ABORT"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr("app.core.security.is_permitted", _allow)
    monkeypatch.setattr("app.api.v1.data_sync.is_permitted", _allow)

    yield {"factory": Sf}

    app.dependency_overrides.clear()
    await test_engine.dispose()


async def _seed_pipeline_with_jobs(
    Sf,
    *,
    states: list[IngestionState],
    pipeline_id=None,
    locked_by: str | None = TEST_POD_ID,
):
    """Seed one ``Pipeline`` row + one ``DataIngestionJob`` per state.

    Each job carries ``locked_by`` so the cleared-lock assertion has
    something to observe.  Returns ``(pipeline_id, [job_ids])`` in
    insertion order so callers can map back to the seeded states.
    """
    pid = pipeline_id or uuid4()
    job_ids: list[int] = []
    async with Sf() as s:
        s.add(
            Pipeline(
                id=pid,
                kind="csv_ingest",
                status=PipelineStatus.RUNNING,
                created_at=datetime.now(timezone.utc),
            )
        )
        # Flush the pipeline row before the children — autoflush
        # dependency ordering can otherwise emit the job INSERT first
        # and trip the FK on ``data_ingestion_jobs.pipeline_id``.
        await s.flush()
        for idx, st in enumerate(states):
            job = DataIngestionJob(
                entity_type=EntityType.MODULE_PER_YEAR,
                module_type_id=int(ModuleTypeEnum.purchase),
                year=2025,
                target_type=TargetType.DATA_ENTRIES,
                ingestion_method=IngestionMethod.csv,
                provider=UserProvider.DEFAULT,
                state=st,
                # Terminal jobs carry a result; non-terminal don't.
                result=(
                    IngestionResult.SUCCESS if st == IngestionState.FINISHED else None
                ),
                is_current=True,
                pipeline_id=pid,
                job_type="csv_ingest" if idx == 0 else "emission_recalc",
                locked_by=locked_by,
                meta={"seed_idx": idx},
            )
            s.add(job)
            await s.flush()
            job_ids.append(job.id)
        await s.commit()
    return pid, job_ids


@pytest.mark.asyncio
async def test_abort_pipeline_flips_non_terminal_jobs(pg_app):
    """Happy path: RUNNING + QUEUED + NOT_STARTED jobs of a pipeline
    flip to FINISHED+ERROR with ``meta.aborted=True``; an already-
    FINISHED job in the same pipeline is left untouched.
    """
    Sf = pg_app["factory"]
    pid, ids = await _seed_pipeline_with_jobs(
        Sf,
        states=[
            IngestionState.RUNNING,  # csv_ingest parent
            IngestionState.QUEUED,  # emission_recalc child A
            IngestionState.NOT_STARTED,  # emission_recalc child B
            IngestionState.FINISHED,  # an already-done sibling
        ],
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(ABORT_URL_TEMPLATE.format(pipeline_id=pid))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pipeline_id"] == str(pid)
    assert body["aborted_by"] == TEST_USER_EMAIL
    # First three were non-terminal; fourth was already FINISHED.
    assert set(body["aborted_job_ids"]) == set(ids[:3])

    async with Sf() as s:
        for jid in ids[:3]:
            row = await s.get(DataIngestionJob, jid)
            assert row is not None
            assert row.state == IngestionState.FINISHED
            assert row.result == IngestionResult.ERROR
            assert row.status_message == f"Aborted by {TEST_USER_EMAIL}"
            assert (row.meta or {}).get("aborted") is True
            assert (row.meta or {}).get("aborted_by") == TEST_USER_EMAIL
            assert row.finished_at is not None
            assert row.is_current is False

        # The pre-FINISHED sibling MUST be untouched (no meta.aborted,
        # original status_message, original result).
        already_done = await s.get(DataIngestionJob, ids[3])
        assert already_done is not None
        assert already_done.result == IngestionResult.SUCCESS
        assert (already_done.meta or {}).get("aborted") is None


@pytest.mark.asyncio
async def test_abort_pipeline_clears_locked_by_so_handler_preemption_trips(pg_app):
    """Load-bearing invariant: ``locked_by`` MUST be cleared on the
    aborted rows.

    The runner's preemption check (``runner.py:270``) reads
    ``current.locked_by != POD_ID`` to decide whether to roll back its
    data writes.  If abort leaves ``locked_by`` alone, an in-flight
    handler completes normally and overwrites our FINISHED+ERROR with
    FINISHED+SUCCESS — operator clicks abort, sees the badge change,
    then watches it flip back to "success" seconds later.  This test
    is the regression guard for that specific UX disaster.
    """
    Sf = pg_app["factory"]
    pid, ids = await _seed_pipeline_with_jobs(
        Sf,
        states=[IngestionState.RUNNING],
        locked_by=TEST_POD_ID,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(ABORT_URL_TEMPLATE.format(pipeline_id=pid))

    assert resp.status_code == 200, resp.text
    async with Sf() as s:
        row = await s.get(DataIngestionJob, ids[0])
        assert row is not None
        assert row.locked_by is None, (
            f"abort_pipeline must clear locked_by (was {row.locked_by!r}); "
            "without this the handler's preemption check at runner.py:270 "
            "doesn't trip and the handler will overwrite our abort with "
            "its own terminal write."
        )


@pytest.mark.asyncio
async def test_abort_pipeline_returns_409_when_all_terminal(pg_app):
    """Every job already FINISHED → nothing to abort → 409, not 200.

    Surfacing 409 instead of an empty 200 lets the frontend show a
    "nothing to stop" toast rather than silently no-oping; an operator
    clicking abort on a pipeline they think is in-flight deserves to
    learn it actually finished.
    """
    Sf = pg_app["factory"]
    pid, _ids = await _seed_pipeline_with_jobs(
        Sf, states=[IngestionState.FINISHED, IngestionState.FINISHED]
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(ABORT_URL_TEMPLATE.format(pipeline_id=pid))

    assert resp.status_code == 409, resp.text
    assert "no non-terminal" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_abort_pipeline_returns_404_for_unknown_pipeline(pg_app):
    """Unknown ``pipeline_id`` → 404 with the pipeline_id echoed back."""
    unknown = uuid4()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(ABORT_URL_TEMPLATE.format(pipeline_id=unknown))

    assert resp.status_code == 404, resp.text
    assert str(unknown) in resp.json()["detail"]
