"""Integration test for ``GET /v1/sync/pipelines/{pipeline_id}/stream`` (PG).

Plan 310D — backend half of the stale-stats UX.  Mirrors the read endpoint
test in ``test_sync_pipeline_endpoint_pg.py``: same auth fixture pattern,
same pipeline-id seeding, same Postgres rationale (native ``UUID`` column,
enum types, asyncpg round-trip).

Coverage scope: the *contract* assertions (404 short-circuit before the
stream opens, 403 permission gate) — not the streaming body.

**Streaming-body coverage is deferred.**  The pre-existing
``GET /sync/jobs/{job_id}/stream`` endpoint (which this one mirrors) also
ships without integration coverage — running ``StreamingResponse`` through
``httpx.ASGITransport`` against an asyncpg-backed test engine triggers
``InterfaceError: connection is closed`` when the FastAPI dep teardown
races with the generator's queries on the same engine, regardless of pool
class.  Producing a stable streaming-body test would require either
extracting the snapshot/poll logic for direct unit-testing or moving the
session lifetime out of ``Depends(get_db)`` for SSE endpoints — a
codebase-wide refactor not in this PR's scope.  The repo-level unit tests
in ``tests/unit/repositories/test_data_ingestion_repo.py`` cover the data
shape; the contract tests below cover gating and not-found.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
import app.api.v1.data_sync as data_sync_module
import app.core.security as security_module
from app.main import app
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres + bypass auth.

    Same shape as ``test_sync_pipeline_endpoint_pg.py``: the 403 test
    bypasses this fixture so the real permission gate fires.

    The SSE handlers open ``db_module.SessionLocal()`` per-iteration to
    avoid pinning a pool slot for the whole stream lifetime, so we
    monkeypatch the module-level ``SessionLocal`` to point at the test
    engine in addition to overriding ``Depends(get_db)`` for non-SSE
    endpoints in this file.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr("app.core.security.is_permitted", _allow)
    # SSE handlers import SessionLocal as ``db_module.SessionLocal``;
    # patch the attribute on the imported module so the per-iteration
    # session opens in the test container.
    monkeypatch.setattr(data_sync_module.db_module, "SessionLocal", Sf)

    async def _allow_module(*_args, **_kwargs):
        return None

    # Pipeline scope check uses the module-level permission gate; bypass
    # it in pg_app so generic streaming-contract tests reach the body.
    # The cross-tenant test below exercises the real check.
    monkeypatch.setattr(data_sync_module, "check_module_permission", _allow_module)

    yield {"factory": Sf, "engine": engine}

    app.dependency_overrides.clear()
    await engine.dispose()


def _make_pending_factor_job(pipeline_id) -> DataIngestionJob:
    """Active (NOT_STARTED) parent — the chain head, not yet picked up."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=1,
        data_entry_type_id=1,
        year=2025,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.NOT_STARTED,
        is_current=True,
        pipeline_id=pipeline_id,
        job_type="factor_ingest",
    )


@pytest.mark.asyncio
async def test_pipeline_stream_unknown_pipeline_returns_404(pg_app):
    """Unknown pipeline_id → 404 *before* the stream opens.

    The endpoint short-circuits with ``HTTPException`` so SSE clients see
    a proper HTTP error, not a 200-with-empty-body that they would
    interpret as an aborted connection.  Symmetric with the
    not-found contract on the read endpoint.
    """
    unknown = uuid4()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/v1/sync/pipelines/{unknown}/stream")

    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_pipeline_stream_returns_403_for_user_without_permission(
    pg_dsn, monkeypatch
):
    """Permission gate matches the read endpoint's
    ``backoffice.data_management.view``.

    Bypasses ``pg_app`` (which monkeypatches ``is_permitted`` to True)
    so the real ``require_permission`` dependency fires.  We still seed
    a job so a permitted user *would* have hit a 200 — proves the 403
    stems from the gate, not from the not-found short-circuit running
    first.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    pipeline_id = uuid4()
    async with Sf() as session:
        session.add(_make_pending_factor_job(pipeline_id))
        await session.commit()

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _deny(*_args, **_kwargs):
        return False

    monkeypatch.setattr("app.core.security.is_permitted", _deny)

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"/v1/sync/pipelines/{pipeline_id}/stream")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_list_jobs_by_pipeline_id_reflects_cross_session_updates(pg_dsn):
    """The SSE poll loop reuses one long-lived session and re-calls
    ``list_jobs_by_pipeline_id`` per tick.  In production the runner
    writes job state changes (claim, FINISHED, status_message,
    started_at) on its OWN ``SessionLocal()`` connection — a different
    session from the SSE handler's.  Without ``populate_existing=True``
    on the repo's select, SQLAlchemy's identity map would serve the SSE
    session a stale cached row on every poll, the change-detection
    (``snapshot != last_snapshot``) would never fire, and the stream
    would emit nothing until the connection finally drops.

    This test pins the contract directly at the repo level (no httpx,
    no SSE) — bot review on PR #1052 caught that the streaming-body
    integration coverage was deferred and the staleness bug slipped
    through.  Two real PG sessions on the same engine reproduce the
    exact mismatch the runner+SSE handler experience.
    """
    from app.repositories.data_ingestion import DataIngestionRepository

    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    pipeline_id = uuid4()

    # Seed: a NOT_STARTED parent job — the kind the SSE consumer sees
    # before the runner picks it up.
    async with Sf() as seed_session:
        seed_session.add(_make_pending_factor_job(pipeline_id))
        await seed_session.commit()

    try:
        # SSE-side session: long-lived, polls repeatedly.
        async with Sf() as sse_session:
            repo = DataIngestionRepository(sse_session)

            # First poll — populates the identity map with the
            # NOT_STARTED row.
            first_snapshot = await repo.list_jobs_by_pipeline_id(pipeline_id)
            assert len(first_snapshot) == 1
            assert first_snapshot[0].state == IngestionState.RUNNING or (
                first_snapshot[0].state == IngestionState.NOT_STARTED
            )
            initial_state = first_snapshot[0].state

            # Out-of-band: simulate the runner claiming the job from a
            # SEPARATE session/connection — exactly what
            # ``run_job → claim_job`` does in production.
            async with Sf() as runner_session:
                runner_repo = DataIngestionRepository(runner_session)
                target = (await runner_repo.list_jobs_by_pipeline_id(pipeline_id))[0]
                assert target.id is not None
                await runner_repo.update_ingestion_job(
                    target.id,
                    status_message="claimed by pod-test",
                    metadata={"phase": "claimed"},
                    state=IngestionState.RUNNING,
                )
                await runner_session.commit()

            # Second poll on the SSE session.  Without
            # ``populate_existing=True`` on the select, SQLAlchemy's
            # identity map would short-circuit the row reload and we'd
            # see the original NOT_STARTED state cached from the first
            # poll — the SSE stream would emit nothing.
            second_snapshot = await repo.list_jobs_by_pipeline_id(pipeline_id)
            assert len(second_snapshot) == 1
            assert second_snapshot[0].state == IngestionState.RUNNING, (
                f"Expected RUNNING after out-of-band claim, got "
                f"{second_snapshot[0].state}.  Identity-map staleness "
                f"regression — populate_existing=True missing on the "
                f"select in DataIngestionRepository.list_jobs_by_pipeline_id."
            )
            assert second_snapshot[0].state != initial_state
            assert second_snapshot[0].status_message == "claimed by pod-test"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_disconnect_releases_pool_slot(pg_dsn, monkeypatch):
    """Client disconnect mid-stream releases the asyncpg pool slot.

    Regression for the SSE pool-pinning bug: the previous implementation
    captured ``Depends(get_db)`` for the entire generator lifetime, so a
    long-running stream pinned one asyncpg pool slot per subscriber for
    minutes.  The fix opens ``SessionLocal()`` per poll iteration and
    checks ``request.is_disconnected()`` at the top of each loop so the
    generator exits promptly when the client aborts.

    We exercise the route's generator directly (rather than via httpx
    streaming, which has flaky cancellation semantics through
    ``ASGITransport``): a fake ``Request`` flips ``is_disconnected`` to
    True after one yield, the generator must exit, and the engine's pool
    must show zero checked-out connections.
    """
    # ``NullPool`` would dispose connections immediately and short-circuit
    # the regression we're trying to catch.  Use the default pool with a
    # tight ``pool_size`` so a single leaked checkout is observable.
    engine = create_async_engine(pg_dsn, future=True, pool_size=2, max_overflow=0)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    pipeline_id = uuid4()
    async with Sf() as session:
        session.add(_make_pending_factor_job(pipeline_id))
        await session.commit()

    # Patch the SSE handler's SessionLocal at the imported-module attribute.
    monkeypatch.setattr(data_sync_module.db_module, "SessionLocal", Sf)

    # Fake Request: flips disconnected after the first poll iteration so
    # the generator's check at the top of iteration 2 exits the loop.
    calls = {"n": 0}

    class _FakeRequest:
        async def is_disconnected(self) -> bool:
            calls["n"] += 1
            return calls["n"] > 1

    fake_user = MagicMock()
    fake_user.id = 1

    # Bypass the per-pipeline scope check for this test — we're testing
    # pool/disconnect behavior, not auth.
    async def _allow_module(*_args, **_kwargs):
        return None

    monkeypatch.setattr(data_sync_module, "check_module_permission", _allow_module)

    try:
        # Baseline: pool starts with zero checkouts (after the seed
        # commit returns its connection on ``async with`` exit).
        assert engine.pool.checkedout() == 0, (
            f"Pool dirty before test: {engine.pool.checkedout()} checkouts"
        )

        response = await data_sync_module.pipeline_stream_by_id(
            pipeline_id=pipeline_id,
            request=_FakeRequest(),
            current_user=fake_user,
        )

        # Drive the generator: collect events until it exits.  With our
        # fake request flipping disconnected on iteration 2, this should
        # complete in a single poll cycle plus the 2s sleep.
        events: list[bytes] = []
        async for chunk in response.body_iterator:
            events.append(chunk if isinstance(chunk, bytes) else chunk.encode())
            # Safety: don't loop forever if the disconnect path regresses.
            if len(events) > 10:
                break

        assert events, "Generator emitted no events before disconnect"
        # The first event should be the initial pipeline snapshot.
        assert b"pipeline-update" in events[0]

        # The fix's contract: per-iteration sessions return their pool
        # slot before each ``asyncio.sleep`` and the generator exits when
        # ``is_disconnected`` flips.  After the iterator drains, no slot
        # is checked out.  The pre-fix code would still hold one slot
        # (the ``Depends(get_db)`` connection) until the response is
        # garbage collected — visible here as ``checkedout() == 1``.
        assert engine.pool.checkedout() == 0, (
            f"Pool slot leaked after disconnect: "
            f"{engine.pool.checkedout()} checkouts still held"
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cross_tenant_pipeline_returns_403(pg_dsn, monkeypatch):
    """User A cannot subscribe to user B's pipeline.

    The pipeline scope check derives ``(module_type_id, institutional_id)``
    from the parent job and runs ``check_module_permission`` on top of the
    existing ``backoffice.data_management.view`` global gate.  A user who
    has the global gate but not the per-module scope must see HTTP 403
    instead of receiving the SSE stream.

    Note on setup: ``_check_job_scope`` short-circuits when
    ``_institutional_id_for_job`` returns None (MODULE_PER_YEAR jobs are
    cross-unit by design — see the post-PR-#1078 hot fix that restored
    access for unit-scoped backoffice users).  We therefore monkeypatch
    the resolver to return a fake institutional_id so the per-module
    deny path actually runs against this test's seeded MODULE_PER_YEAR
    job.  The httpx client carries an aggressive timeout so a future
    regression that reopens the streaming path fails fast instead of
    hanging the suite (the previous shape would deadlock here for the
    full test-session timeout).
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    pipeline_id = uuid4()
    async with Sf() as session:
        session.add(_make_pending_factor_job(pipeline_id))
        await session.commit()

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    # Pass the global gate so the per-module check is what fires.
    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr("app.core.security.is_permitted", _allow)
    monkeypatch.setattr(data_sync_module.db_module, "SessionLocal", Sf)

    # Force ``_check_job_scope`` to reach ``check_module_permission`` even
    # though the seeded job is MODULE_PER_YEAR (which would normally
    # short-circuit at ``institutional_id is None``).
    async def _resolve_institutional_id(*_args, **_kwargs):
        return "FAKE-CROSS-TENANT-INST"

    monkeypatch.setattr(
        data_sync_module, "_institutional_id_for_job", _resolve_institutional_id
    )

    # Per-module check denies — this is the cross-tenant simulation.
    async def _deny_module(*_args, **_kwargs):
        raise HTTPException(
            status_code=403,
            detail="Permission denied: cross-tenant pipeline",
        )

    monkeypatch.setattr(data_sync_module, "check_module_permission", _deny_module)

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            # Cap each request at 10s — if the scope check ever regresses
            # the stream endpoint would block on its 2s polling loop.
            # Better to fail fast than hang the daily integration CI.
            timeout=httpx.Timeout(10.0),
        ) as client:
            stream_resp = await client.get(f"/v1/sync/pipelines/{pipeline_id}/stream")
            read_resp = await client.get(f"/v1/sync/pipelines/{pipeline_id}")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert stream_resp.status_code == 403, stream_resp.text
    assert read_resp.status_code == 403, read_resp.text
