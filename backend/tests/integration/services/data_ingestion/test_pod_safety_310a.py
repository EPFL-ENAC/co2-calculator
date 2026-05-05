"""Integration tests for Plan 310A: Pod Safety + Atomic Claim (SQLite).

Tests cover:
- claim_job: success, duplicate, max_attempts, finished, is_current unsetting
- recover_job: stale, not stale, atomic UPDATE
- run_sync_task: claim guard (provider not invoked on claim failure)
- run_recalculation_task: claim guard
- POST /jobs/{id}/recover endpoint: stale, not stale, not RUNNING
- poll_pending_jobs: picks up orphan, dispatches by job_type
- dispatch_job: routes to correct handler per job_type

The true concurrent-claim race (partial unique index → IntegrityError) is
covered separately in ``test_pod_safety_310a_pg.py`` against a real
Postgres container — SQLite cannot reproduce that contention.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.testclient import TestClient

from app.main import app
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks.emission_recalculation_tasks import run_recalculation_task
from app.tasks.ingestion_tasks import run_sync_task


def _make_job(
    state: IngestionState = IngestionState.NOT_STARTED,
    result: IngestionResult | None = None,
    is_current: bool = False,
    locked_by: str | None = None,
    locked_at: datetime | None = None,
    attempts: int = 0,
    max_attempts: int = 3,
    run_after: datetime | None = None,
    module_type_id: int = 1,
    data_entry_type_id: int = 1,
    year: int = 2025,
    target_type: TargetType = TargetType.DATA_ENTRIES,
    ingestion_method: IngestionMethod = IngestionMethod.csv,
    job_type: str | None = None,
    meta: dict | None = None,
) -> DataIngestionJob:
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        data_entry_type_id=data_entry_type_id,
        year=year,
        target_type=target_type,
        ingestion_method=ingestion_method,
        provider=UserProvider.DEFAULT,
        state=state,
        result=result,
        is_current=is_current,
        locked_by=locked_by,
        locked_at=locked_at,
        attempts=attempts,
        max_attempts=max_attempts,
        run_after=run_after,
        job_type=job_type,
        meta=meta or {},
    )


# ======================================================================
# claim_job tests
# ======================================================================


@pytest.mark.asyncio
async def test_claim_job_success(db_session: AsyncSession):
    job = _make_job(state=IngestionState.NOT_STARTED)
    db_session.add(job)
    await db_session.flush()
    job_id = job.id

    repo = DataIngestionRepository(db_session)
    claimed = await repo.claim_job(job_id, "pod-1")

    assert claimed is True
    refreshed = await repo.get_job_by_id(job_id)
    assert refreshed.state == IngestionState.RUNNING
    assert refreshed.locked_by == "pod-1"
    assert refreshed.is_current is True
    assert refreshed.attempts == 1
    assert refreshed.locked_at is not None


@pytest.mark.asyncio
async def test_claim_job_duplicate_claim(db_session: AsyncSession):
    job = _make_job(state=IngestionState.NOT_STARTED)
    db_session.add(job)
    await db_session.flush()
    job_id = job.id

    repo = DataIngestionRepository(db_session)
    claimed1 = await repo.claim_job(job_id, "pod-1")
    claimed2 = await repo.claim_job(job_id, "pod-2")

    assert claimed1 is True
    assert claimed2 is False


@pytest.mark.asyncio
async def test_claim_job_exceeds_max_attempts(db_session: AsyncSession):
    job = _make_job(
        state=IngestionState.NOT_STARTED,
        attempts=3,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.flush()

    repo = DataIngestionRepository(db_session)
    claimed = await repo.claim_job(job.id, "pod-1")
    assert claimed is False


@pytest.mark.asyncio
async def test_claim_job_already_finished(db_session: AsyncSession):
    job = _make_job(
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
    )
    db_session.add(job)
    await db_session.flush()

    repo = DataIngestionRepository(db_session)
    claimed = await repo.claim_job(job.id, "pod-1")
    assert claimed is False


@pytest.mark.asyncio
async def test_claim_job_none_id(db_session: AsyncSession):
    repo = DataIngestionRepository(db_session)
    claimed = await repo.claim_job(99999, "pod-1")
    assert claimed is False


@pytest.mark.asyncio
async def test_claim_job_respects_future_run_after(db_session: AsyncSession):
    """Jobs scheduled for the future (e.g. retry backoff) must not be
    claimable until ``run_after`` has elapsed."""
    job = _make_job(
        state=IngestionState.NOT_STARTED,
        run_after=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(job)
    await db_session.flush()
    assert job.id is not None

    repo = DataIngestionRepository(db_session)
    claimed = await repo.claim_job(job.id, "pod-1")
    assert claimed is False

    refreshed = await repo.get_job_by_id(job.id)
    assert refreshed is not None
    assert refreshed.state == IngestionState.NOT_STARTED
    assert refreshed.locked_by is None
    assert refreshed.attempts == 0


@pytest.mark.asyncio
async def test_claim_job_succeeds_when_run_after_has_elapsed(
    db_session: AsyncSession,
):
    """Once ``run_after`` is in the past, the job becomes claimable."""
    job = _make_job(
        state=IngestionState.NOT_STARTED,
        run_after=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(job)
    await db_session.flush()
    assert job.id is not None

    repo = DataIngestionRepository(db_session)
    claimed = await repo.claim_job(job.id, "pod-1")
    assert claimed is True

    refreshed = await repo.get_job_by_id(job.id)
    assert refreshed is not None
    assert refreshed.state == IngestionState.RUNNING
    assert refreshed.locked_by == "pod-1"


# Note: the "unset previous is_current for the same combo" behavior cannot
# be exercised in SQLite — `postgresql_where` is a dialect-specific kwarg
# and SQLite ignores it, so the unique index becomes a *full* unique index
# on the combo columns.  Two same-combo rows can't coexist there, even with
# different is_current values.  See ``test_pod_safety_310a_pg.py``'s
# ``test_claim_demotes_finished_sibling`` for the real coverage on Postgres.


# ======================================================================
# recover_job tests
# ======================================================================


@pytest.mark.asyncio
async def test_recover_job_stale(db_session: AsyncSession):
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=60)
    job = _make_job(
        state=IngestionState.RUNNING,
        locked_by="pod-crashed",
        locked_at=stale_time,
        attempts=1,
        is_current=True,
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.flush()
    job_id = job.id

    repo = DataIngestionRepository(db_session)
    recovered = await repo.recover_job(job_id, stale_timeout_minutes=30)

    assert recovered is not None
    assert recovered.state == IngestionState.NOT_STARTED
    assert recovered.locked_by is None
    assert recovered.locked_at is None
    assert recovered.is_current is False
    assert recovered.attempts == 0
    assert recovered.run_after is None


@pytest.mark.asyncio
async def test_recover_job_not_stale(db_session: AsyncSession):
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    job = _make_job(
        state=IngestionState.RUNNING,
        locked_by="pod-alive",
        locked_at=recent_time,
    )
    db_session.add(job)
    await db_session.flush()

    repo = DataIngestionRepository(db_session)
    recovered = await repo.recover_job(job.id, stale_timeout_minutes=30)
    assert recovered is None


@pytest.mark.asyncio
async def test_recover_job_not_running(db_session: AsyncSession):
    job = _make_job(state=IngestionState.FINISHED, result=IngestionResult.SUCCESS)
    db_session.add(job)
    await db_session.flush()

    repo = DataIngestionRepository(db_session)
    recovered = await repo.recover_job(job.id, stale_timeout_minutes=0)
    assert recovered is None


@pytest.mark.asyncio
async def test_recover_job_none_id(db_session: AsyncSession):
    repo = DataIngestionRepository(db_session)
    recovered = await repo.recover_job(99999, stale_timeout_minutes=0)
    assert recovered is None


# ======================================================================
# sweep_stuck_running_jobs tests (poller's pod-crash auto-recovery)
# ======================================================================
#
# Difference from ``recover_job``: the sweep PRESERVES ``attempts`` so
# claim_job's max-retry guard caps an infinitely-crashing job, and it
# ABANDONS jobs whose attempts have hit max (state=FINISHED+ERROR) so
# operators see them.  ``recover_job`` (the manual API path) intentionally
# resets attempts to 0 — operator override of the cap.


@pytest.mark.asyncio
async def test_sweep_recovers_stuck_running_with_retries_left(
    db_session: AsyncSession,
):
    """attempts < max → reset to NOT_STARTED but PRESERVE attempts.

    Locks are cleared so claim_job can pick it up next cycle, but
    attempts is intact so a job that crashes every time can't loop
    forever — claim_job's ``attempts < max_attempts`` guard caps it.
    """
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=60)
    job = _make_job(
        state=IngestionState.RUNNING,
        locked_by="pod-crashed-1",
        locked_at=stale_time,
        attempts=1,
        max_attempts=3,
        is_current=True,
    )
    db_session.add(job)
    await db_session.flush()
    job_id = job.id

    repo = DataIngestionRepository(db_session)
    recovered, abandoned = await repo.sweep_stuck_running_jobs(stale_timeout_minutes=30)
    assert (recovered, abandoned) == (1, 0)

    refreshed = await repo.get_job_by_id(job_id)
    assert refreshed is not None
    assert refreshed.state == IngestionState.NOT_STARTED
    assert refreshed.locked_by is None
    assert refreshed.locked_at is None
    assert refreshed.is_current is False
    assert refreshed.run_after is None
    # attempts is preserved — that's the whole difference vs recover_job
    assert refreshed.attempts == 1


@pytest.mark.asyncio
async def test_sweep_abandons_stuck_running_at_max_attempts(
    db_session: AsyncSession,
):
    """attempts >= max → mark FINISHED+ERROR with diagnostic message.

    Without this branch, a job whose handler crashes every claim would
    sit RUNNING forever after attempts hits max — claim_job won't
    re-pick it up (``attempts < max_attempts`` is false), and the
    recoverable branch above won't fire either (same gate).  So we
    mark it terminally failed; operators see it and can investigate.
    """
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=60)
    job = _make_job(
        state=IngestionState.RUNNING,
        locked_by="pod-crashed-final",
        locked_at=stale_time,
        attempts=3,
        max_attempts=3,
        is_current=True,
    )
    db_session.add(job)
    await db_session.flush()
    job_id = job.id

    repo = DataIngestionRepository(db_session)
    recovered, abandoned = await repo.sweep_stuck_running_jobs(stale_timeout_minutes=30)
    assert (recovered, abandoned) == (0, 1)

    refreshed = await repo.get_job_by_id(job_id)
    assert refreshed is not None
    assert refreshed.state == IngestionState.FINISHED
    assert refreshed.result == IngestionResult.ERROR
    assert "Auto-recovery" in (refreshed.status_message or "")
    assert "max_attempts" in (refreshed.status_message or "")


@pytest.mark.asyncio
async def test_sweep_skips_running_within_stale_window(db_session: AsyncSession):
    """Jobs whose locked_at is within the stale window are presumed alive."""
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    job = _make_job(
        state=IngestionState.RUNNING,
        locked_by="pod-alive",
        locked_at=recent_time,
        attempts=1,
    )
    db_session.add(job)
    await db_session.flush()

    repo = DataIngestionRepository(db_session)
    recovered, abandoned = await repo.sweep_stuck_running_jobs(stale_timeout_minutes=30)
    assert (recovered, abandoned) == (0, 0)

    refreshed = await repo.get_job_by_id(job.id)
    assert refreshed is not None
    assert refreshed.state == IngestionState.RUNNING  # untouched


@pytest.mark.asyncio
async def test_sweep_recovers_running_with_null_locked_at(db_session: AsyncSession):
    """RUNNING with NULL locked_at = a clearly-broken row (claim_job
    always sets locked_at on success).  Treat as stale and recover."""
    job = _make_job(
        state=IngestionState.RUNNING,
        locked_by="pod-mystery",
        locked_at=None,
        attempts=1,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.flush()

    repo = DataIngestionRepository(db_session)
    recovered, abandoned = await repo.sweep_stuck_running_jobs(stale_timeout_minutes=30)
    assert (recovered, abandoned) == (1, 0)


@pytest.mark.asyncio
async def test_sweep_does_not_touch_not_started(db_session: AsyncSession):
    """NOT_STARTED is the dispatch sweep's domain — auto-recovery only
    cares about RUNNING."""
    job = _make_job(state=IngestionState.NOT_STARTED, attempts=0)
    db_session.add(job)
    await db_session.flush()

    repo = DataIngestionRepository(db_session)
    recovered, abandoned = await repo.sweep_stuck_running_jobs(stale_timeout_minutes=30)
    assert (recovered, abandoned) == (0, 0)


@pytest.mark.asyncio
async def test_sweep_handles_mixed_population(db_session: AsyncSession):
    """One sweep call handles multiple rows in different buckets without
    interference — recoverable, abandoned, alive, and not-started all
    coexist; only the first two are touched."""
    stale = datetime.now(timezone.utc) - timedelta(minutes=60)
    fresh = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.add_all(
        [
            _make_job(
                state=IngestionState.RUNNING,
                locked_at=stale,
                attempts=1,
                max_attempts=3,
                module_type_id=1,
            ),
            _make_job(
                state=IngestionState.RUNNING,
                locked_at=stale,
                attempts=3,
                max_attempts=3,
                module_type_id=2,
            ),
            _make_job(
                state=IngestionState.RUNNING,
                locked_at=fresh,
                attempts=1,
                module_type_id=3,
            ),
            _make_job(state=IngestionState.NOT_STARTED, module_type_id=4),
        ]
    )
    await db_session.flush()

    repo = DataIngestionRepository(db_session)
    recovered, abandoned = await repo.sweep_stuck_running_jobs(stale_timeout_minutes=30)
    assert (recovered, abandoned) == (1, 1)


# ======================================================================
# run_sync_task claim guard tests
# ======================================================================


@pytest.mark.asyncio
async def test_run_sync_task_claim_fails_skips_provider(db_session: AsyncSession):
    job = _make_job(
        state=IngestionState.NOT_STARTED,
        locked_by="other-pod",
    )
    db_session.add(job)
    await db_session.flush()

    fake_provider = MagicMock()
    fake_provider.ingest = AsyncMock()
    fake_provider._update_job = AsyncMock()
    fake_provider.set_job_id = AsyncMock()

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch("app.tasks.ingestion_tasks.SessionLocal") as mock_session_local,
        patch(
            "app.tasks.ingestion_tasks.ProviderFactory.get_provider_class",
            return_value=FakeProviderClass,
        ),
    ):
        mock_job_session = db_session
        mock_data_session = MagicMock()
        mock_data_session.commit = AsyncMock()
        mock_data_session.rollback = AsyncMock()

        mock_session_local.return_value.__aenter__ = AsyncMock(
            side_effect=[mock_job_session, mock_data_session]
        )
        mock_session_local.return_value.__aexit__ = AsyncMock(return_value=None)

        await run_sync_task(
            "FakeProviderClass", job_id=job.id, filters={"key": "value"}
        )

    fake_provider.ingest.assert_not_called()


@pytest.mark.asyncio
async def test_run_sync_task_invalid_provider_does_not_claim(
    db_session: AsyncSession,
):
    """If the provider class doesn't resolve, ``run_sync_task`` must
    return BEFORE acquiring the claim — otherwise the job ends up stuck
    in RUNNING and only the 30-min stale-recovery window can release it.
    """
    job = _make_job(state=IngestionState.NOT_STARTED)
    db_session.add(job)
    await db_session.flush()
    assert job.id is not None

    with patch("app.tasks.ingestion_tasks.SessionLocal") as mock_session_local:
        mock_data_session = MagicMock()
        mock_data_session.commit = AsyncMock()
        mock_data_session.rollback = AsyncMock()
        mock_session_local.return_value.__aenter__ = AsyncMock(
            side_effect=[db_session, mock_data_session]
        )
        mock_session_local.return_value.__aexit__ = AsyncMock(return_value=None)

        # No patch on ProviderFactory: the real factory returns None for
        # this bogus name, which is exactly what we want to exercise.
        await run_sync_task(
            "DefinitelyNotAProviderClass",
            job_id=job.id,
            filters={},
        )

    # Job must be untouched — no claim occurred.
    repo = DataIngestionRepository(db_session)
    refreshed = await repo.get_job_by_id(job.id)
    assert refreshed is not None
    assert refreshed.state == IngestionState.NOT_STARTED
    assert refreshed.is_current is False
    assert refreshed.locked_by is None
    assert refreshed.attempts == 0


# ======================================================================
# run_recalculation_task claim guard tests
# ======================================================================


@pytest.mark.asyncio
async def test_run_recalculation_task_claim_fails(db_session: AsyncSession):
    job = _make_job(
        state=IngestionState.NOT_STARTED,
        locked_by="other-pod",
    )
    db_session.add(job)
    await db_session.flush()

    with patch("app.tasks.emission_recalculation_tasks.SessionLocal") as mock_sl:
        mock_job_session = db_session
        mock_data_session = MagicMock()
        mock_data_session.commit = AsyncMock()
        mock_data_session.rollback = AsyncMock()

        mock_sl.return_value.__aenter__ = AsyncMock(
            side_effect=[mock_job_session, mock_data_session]
        )
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=None)

        await run_recalculation_task(
            module_type_id=1,
            data_entry_type_id=1,
            year=2025,
            job_id=job.id,
        )

    refreshed = await DataIngestionRepository(db_session).get_job_by_id(job.id)
    assert refreshed.state == IngestionState.NOT_STARTED


# ======================================================================
# recover endpoint tests
# ======================================================================


@pytest.mark.asyncio
async def test_recover_endpoint_stale(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=60)
    job = _make_job(
        state=IngestionState.RUNNING,
        locked_by="pod-1",
        locked_at=stale_time,
        is_current=True,
    )
    db_session.add(job)
    await db_session.flush()
    job_id = job.id

    from app.api.deps import get_current_user, get_db

    async def fake_user():
        fake = MagicMock()
        fake.institutional_id = "test"
        fake.roles = []
        fake.calculate_permissions = MagicMock(return_value={})
        return fake

    async def fake_permitted(*args, **kwargs):
        return True

    async def fake_get_db():
        yield db_session

    monkeypatch.setattr("app.core.security.is_permitted", fake_permitted)

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_get_db

    try:
        with TestClient(app) as client:
            resp = client.post(f"/api/v1/sync/jobs/{job_id}/recover")

        assert resp.status_code == 200
        assert resp.json()["state"] == IngestionState.NOT_STARTED
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_recover_endpoint_not_stale(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    job = _make_job(
        state=IngestionState.RUNNING,
        locked_by="pod-1",
        locked_at=recent_time,
    )
    db_session.add(job)
    await db_session.flush()

    from app.api.deps import get_current_user, get_db

    async def fake_user():
        fake = MagicMock()
        fake.institutional_id = "test"
        fake.roles = []
        fake.calculate_permissions = MagicMock(return_value={})
        return fake

    async def fake_permitted(*args, **kwargs):
        return True

    async def fake_get_db():
        yield db_session

    monkeypatch.setattr("app.core.security.is_permitted", fake_permitted)

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_get_db

    try:
        with TestClient(app) as client:
            resp = client.post(f"/api/v1/sync/jobs/{job.id}/recover")

        assert resp.status_code == 409
    finally:
        app.dependency_overrides.clear()


# ======================================================================
# poller tests
# ======================================================================


@pytest.mark.asyncio
async def test_pending_jobs_query(db_session: AsyncSession):
    job1 = _make_job(
        state=IngestionState.NOT_STARTED,
        run_after=None,
        locked_by=None,
        attempts=0,
        data_entry_type_id=1,
    )
    job2 = _make_job(
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        data_entry_type_id=2,
    )
    job3 = _make_job(
        state=IngestionState.NOT_STARTED,
        run_after=None,
        locked_by="pod-1",
        attempts=0,
        data_entry_type_id=3,
    )
    job4 = _make_job(
        state=IngestionState.NOT_STARTED,
        run_after=None,
        locked_by=None,
        attempts=3,
        max_attempts=3,
        data_entry_type_id=4,
    )
    for job in (job1, job2, job3, job4):
        db_session.add(job)
    await db_session.flush()

    repo = DataIngestionRepository(db_session)
    stmt = repo._pending_jobs_query(limit=10)
    jobs = (await db_session.execute(stmt)).scalars().all()

    job_ids = {j.id for j in jobs}
    assert job1.id in job_ids
    assert job2.id not in job_ids
    assert job3.id not in job_ids
    assert job4.id not in job_ids


@pytest.mark.asyncio
async def test_dispatch_job_unknown_type(db_session: AsyncSession):
    from app.tasks._poller import dispatch_job

    job = _make_job(
        state=IngestionState.NOT_STARTED,
        job_type="unknown_type",
    )
    db_session.add(job)
    await db_session.flush()

    with patch("app.tasks._poller.logger.warning") as mock_warning:
        await dispatch_job(job, "pod-test")
        mock_warning.assert_called_once()
        assert "unknown_type" in mock_warning.call_args[0][0]
