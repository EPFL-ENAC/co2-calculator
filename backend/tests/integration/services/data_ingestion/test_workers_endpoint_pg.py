"""Regression tests for ``GET /api/v1/sync/workers`` (#1080 sprint-9).

Pins:

1. Live pods (last_heartbeat_at within 2× interval) are returned;
   dead pods are filtered out.  Without the dead-pod filter the
   workers view would show phantom claimers after every crash and
   defeat its purpose as a "who's working right now" signal.
2. Each row carries ``git_sha`` + ``app_version`` straight from the
   pod row — the diagnostic that would have caught the
   2026-05-21 local+stage scenario at a glance.
3. ``claimed_job_count`` reflects the number of RUNNING jobs whose
   ``locked_by`` matches the pod_id — the operator's "this pod is
   actually doing work" indicator.

Requires Docker — see ``conftest.py``'s ``postgres_container``.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
import app.core.security as security_module
from app.core.config import get_settings
from app.main import app
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import ModuleTypeEnum
from app.models.pod import Pod
from app.models.user import UserProvider

WORKERS_URL = "/api/v1/sync/workers"


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire FastAPI to test PG + bypass auth (same pattern as the
    other workers/abort suites in this directory)."""
    psycopg_dsn = pg_dsn.replace("+asyncpg", "+psycopg")
    test_engine = create_async_engine(psycopg_dsn, future=True)
    Sf = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "operator@test.example"
    fake_user.institutional_id = "TEST-WORKERS"

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


def _interval_seconds() -> int:
    return get_settings().POD_HEARTBEAT_INTERVAL_SECONDS


async def _seed_pod(
    Sf,
    *,
    pod_id: str,
    git_sha: str | None = "abc1234",
    app_version: str | None = "1.0.0",
    heartbeat_age_seconds: int = 0,
) -> Pod:
    """Insert a pod row with a controllable ``last_heartbeat_at``
    offset.  ``heartbeat_age_seconds = 0`` → "live right now"; large
    values → "dead" (past the 2× window the endpoint filters by)."""
    now = datetime.now(timezone.utc)
    async with Sf() as s:
        pod = Pod(
            pod_id=pod_id,
            git_sha=git_sha,
            app_version=app_version,
            started_at=now - timedelta(minutes=10),
            last_heartbeat_at=now - timedelta(seconds=heartbeat_age_seconds),
        )
        s.add(pod)
        await s.commit()
        return pod


async def _seed_claimed_job(Sf, *, locked_by: str) -> int:
    """Insert a RUNNING data_ingestion_jobs row claimed by ``locked_by``
    so the workers endpoint's claimed-count subquery has something to
    count.
    """
    async with Sf() as s:
        job = DataIngestionJob(
            entity_type=EntityType.MODULE_PER_YEAR,
            module_type_id=int(ModuleTypeEnum.purchase),
            year=2025,
            target_type=TargetType.DATA_ENTRIES,
            ingestion_method=IngestionMethod.csv,
            provider=UserProvider.DEFAULT,
            state=IngestionState.RUNNING,
            result=IngestionResult.SUCCESS,
            is_current=True,
            job_type="csv_ingest",
            locked_by=locked_by,
            locked_at=datetime.now(timezone.utc),
            meta={},
        )
        s.add(job)
        await s.commit()
        return job.id


@pytest.mark.asyncio
async def test_workers_endpoint_returns_only_live_pods(pg_app):
    """Pod with a fresh heartbeat is returned; pod whose heartbeat
    is stale (older than 2× interval) is filtered out.
    """
    Sf = pg_app["factory"]
    interval = _interval_seconds()
    await _seed_pod(Sf, pod_id="pod-live", heartbeat_age_seconds=interval // 2)
    await _seed_pod(
        Sf,
        pod_id="pod-dead",
        heartbeat_age_seconds=3 * interval,  # well past 2× window
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(WORKERS_URL)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    pod_ids = {row["pod_id"] for row in body}
    assert pod_ids == {"pod-live"}, (
        f"expected only live pod, got {pod_ids}. The endpoint must "
        "filter by last_heartbeat_at within 2× POD_HEARTBEAT_INTERVAL_SECONDS "
        "so dead pods don't show as phantom claimers."
    )


@pytest.mark.asyncio
async def test_workers_endpoint_surfaces_git_sha(pg_app):
    """The git_sha + app_version round-trip — the diagnostic that
    catches the local+stage scenario at a glance."""
    Sf = pg_app["factory"]
    await _seed_pod(
        Sf,
        pod_id="pod-A",
        git_sha="aaaaaaa1234",
        app_version="1.2.3",
    )
    await _seed_pod(
        Sf,
        pod_id="pod-B",
        git_sha="bbbbbbb5678",
        app_version="1.2.4-rc1",
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(WORKERS_URL)

    assert resp.status_code == 200, resp.text
    by_id = {row["pod_id"]: row for row in resp.json()}
    assert by_id["pod-A"]["git_sha"] == "aaaaaaa1234"
    assert by_id["pod-A"]["app_version"] == "1.2.3"
    assert by_id["pod-B"]["git_sha"] == "bbbbbbb5678"
    assert by_id["pod-B"]["app_version"] == "1.2.4-rc1"


@pytest.mark.asyncio
async def test_workers_endpoint_counts_claimed_jobs(pg_app):
    """``claimed_job_count`` returns the number of RUNNING
    data_ingestion_jobs whose ``locked_by`` equals ``pod_id``.

    Without this signal the workers view can't answer "is this pod
    actually doing work, or is it idle?" — the operator's first
    question when diagnosing a stuck chain.
    """
    Sf = pg_app["factory"]
    await _seed_pod(Sf, pod_id="pod-busy")
    await _seed_pod(Sf, pod_id="pod-idle")
    # 2 RUNNING jobs claimed by pod-busy, 0 by pod-idle.
    await _seed_claimed_job(Sf, locked_by="pod-busy")
    await _seed_claimed_job(Sf, locked_by="pod-busy")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(WORKERS_URL)

    assert resp.status_code == 200, resp.text
    by_id = {row["pod_id"]: row for row in resp.json()}
    assert by_id["pod-busy"]["claimed_job_count"] == 2
    assert by_id["pod-idle"]["claimed_job_count"] == 0


@pytest.mark.asyncio
async def test_workers_endpoint_returns_empty_when_no_pods(pg_app):
    """No pods registered → empty list, not 404 (the endpoint is
    always queryable; absence of pods is information, not an
    error)."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(WORKERS_URL)

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_workers_endpoint_tolerates_tz_naive_rows(pg_app):
    """Defensive: a pre-existing ``pods`` table created with plain
    ``TIMESTAMP`` (no TZ) — which a long-lived dev DB will have
    because ``SQLModel.metadata.create_all`` doesn't ALTER existing
    tables — must not 500 the endpoint.

    Reproduces the original report (2026-05-21 user-reported 500 on
    localhost): INSERTing a tz-naive ``last_heartbeat_at`` and
    expecting the endpoint to coerce-on-read.  The fix treats naive
    rows as UTC (matches what the heartbeat writer was always
    producing on the wire — only the column type was different).
    """
    from sqlalchemy import text

    Sf = pg_app["factory"]
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    # Bypass the ORM (which would coerce on write) and write the
    # naive value at the SQL layer — matches what a TIMESTAMP-WITHOUT-
    # TZ column would round-trip on read.
    async with Sf() as s:
        await s.execute(
            text(
                "INSERT INTO pods (pod_id, git_sha, app_version, "
                "started_at, last_heartbeat_at) VALUES "
                "(:pod_id, :sha, :ver, :start, :hb)"
            ),
            {
                "pod_id": "pod-naive",
                "sha": "deadbeef",
                "ver": "1.0.0",
                "start": now_naive,
                "hb": now_naive,
            },
        )
        await s.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(WORKERS_URL)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {r["pod_id"] for r in body} == {"pod-naive"}
    # The naive row should still be considered live (heartbeat age
    # within 2× interval), confirming the coercion path matched the
    # tz-aware filter result.
    assert body[0]["heartbeat_age_seconds"] < 2 * _interval_seconds()
