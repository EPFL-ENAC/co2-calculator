"""Integration test for ``GET /v1/sync/active-pipelines`` against PG.

Plan 310-D / Issue #1062 — bulk read used by the unified frontend
``pipelineStateStore`` to drive the "Recalculating..." badge.  Thin
wrapper over ``DataIngestionRepository.get_current_pipeline_ids_for_modules``;
this IT pins the wire shape (``dict[int, str]`` with sparse keys) plus
permission gating.

Why a real Postgres (not SQLite):

- ``DataIngestionJob.pipeline_id`` is a native ``UUID`` column.  SQLite
  doesn't enforce UUID typing — testing against PG verifies the
  asyncpg round-trip and JSON-string serialisation of UUIDs both work.
- The endpoint filters by ``state IN (NOT_STARTED, QUEUED, RUNNING)``.
  PG enum types must round-trip through the WHERE clause; SQLite stores
  them as plain strings and would hide a mismatch.

Mirrors the auth / dependency-override pattern in
``test_sync_pipeline_endpoint_pg.py`` (the canonical 310-series example).

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

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
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres + bypass auth.

    The 403 test below deliberately bypasses this fixture to exercise the
    real permission gate.
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

    # ``/sync/active-pipelines`` carries TWO permission layers.  The
    # tests in this file pin RESPONSE-SHAPE behaviour (mapping shape,
    # sparse passthrough, year filter, etc.) — they are NOT testing
    # the security filter.  We bypass it here by mocking it to allow.
    # The security filter itself is asserted in a separate test
    # (``test_active_pipelines_returns_403_for_user_without_permission``)
    # that deliberately bypasses this fixture to exercise the real gate.
    #
    # Layer 1 (global): ``require_permission("backoffice.data_management",
    # "view")`` — cleared by mocking ``is_permitted`` above.
    # Layer 2 (per-module): the endpoint loops the requested modules and
    # calls ``get_module_permission_decision(user, module_id, "view")``
    # for each, dropping disallowed entries from the response.  The
    # default test user (a bare ``MagicMock``) holds zero module-level
    # permissions, so without this mock every requested module gets
    # filtered out and the endpoint returns ``{}``.  This is the
    # security guard added in PR #1079 V1 to stop pipeline UUIDs from
    # leaking across modules a caller can't read.
    async def _allow_module_decision(*_args, **_kwargs):
        return {"allow": True}

    monkeypatch.setattr(
        "app.api.v1.data_sync.get_module_permission_decision",
        _allow_module_decision,
    )

    yield {"factory": Sf}

    app.dependency_overrides.clear()
    await engine.dispose()


def _make_active_pipeline_job(
    *,
    module_type_id: int,
    year: int,
    pipeline_id,
    state: IngestionState = IngestionState.RUNNING,
) -> DataIngestionJob:
    """Active aggregation row carrying a ``pipeline_id`` — what the
    repo helper picks as 'currently in flight' for this module/year."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        year=year,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        provider=UserProvider.DEFAULT,
        state=state,
        is_current=True,
        pipeline_id=pipeline_id,
        job_type="aggregation",
        meta={},
    )


@pytest.mark.asyncio
async def test_active_pipelines_returns_mapping_for_requested_modules(pg_app):
    """Two modules each have an active pipeline → endpoint returns a
    ``{module_type_id: pipeline_id}`` dict with both entries as JSON
    strings (UUIDs serialised through the response model)."""
    Sf = pg_app["factory"]
    pipeline_a = uuid4()
    pipeline_b = uuid4()

    async with Sf() as session:
        session.add(
            _make_active_pipeline_job(
                module_type_id=1, year=2025, pipeline_id=pipeline_a
            )
        )
        session.add(
            _make_active_pipeline_job(
                module_type_id=2, year=2025, pipeline_id=pipeline_b
            )
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            "/v1/sync/active-pipelines", params={"year": 2025, "modules": "1,2,3"}
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # JSON object keys are strings even when typed as int in FastAPI.
    assert body == {"1": str(pipeline_a), "2": str(pipeline_b)}


@pytest.mark.asyncio
async def test_active_pipelines_omits_modules_without_active_pipeline(pg_app):
    """Sparse passthrough: modules without an active pipeline are absent
    from the response.  Frontend uses ``.get(...)`` and treats missing
    keys as 'no badge'."""
    Sf = pg_app["factory"]

    async with Sf() as session:
        # Only module 1 has an active pipeline.
        session.add(
            _make_active_pipeline_job(module_type_id=1, year=2025, pipeline_id=uuid4())
        )
        # Module 2 has a FINISHED pipeline (excluded by the helper).
        session.add(
            _make_active_pipeline_job(
                module_type_id=2,
                year=2025,
                pipeline_id=uuid4(),
                state=IngestionState.FINISHED,
            )
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            "/v1/sync/active-pipelines", params={"year": 2025, "modules": "1,2"}
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "1" in body
    assert "2" not in body


@pytest.mark.asyncio
async def test_active_pipelines_filters_by_year(pg_app):
    """A pipeline running for a different year must NOT appear in the
    requested year's response — guards the badge from cross-year
    bleed."""
    Sf = pg_app["factory"]

    async with Sf() as session:
        # Active pipeline but for 2024 — the request asks for 2025.
        session.add(
            _make_active_pipeline_job(module_type_id=1, year=2024, pipeline_id=uuid4())
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            "/v1/sync/active-pipelines", params={"year": 2025, "modules": "1"}
        )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {}


@pytest.mark.asyncio
async def test_active_pipelines_empty_modules_returns_empty_dict(pg_app):
    """``modules=`` (empty) short-circuits to an empty dict without
    firing the SELECT — defensive against the frontend sending an
    empty list before any modules are known."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            "/v1/sync/active-pipelines", params={"year": 2025, "modules": ""}
        )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {}


@pytest.mark.asyncio
async def test_active_pipelines_invalid_modules_returns_400(pg_app):
    """Non-integer ``modules`` token → 400, not a 500 from int()."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(
            "/v1/sync/active-pipelines", params={"year": 2025, "modules": "1,abc"}
        )

    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_active_pipelines_returns_403_for_user_without_permission(
    pg_dsn, monkeypatch
):
    """``GET /v1/sync/active-pipelines`` is gated behind
    ``backoffice.data_management.view``.  Users without that permission
    get HTTP 403.

    Deliberately bypasses ``pg_app`` (which monkeypatches ``is_permitted``
    to always-True) so the real permission check fires.
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

    async def _deny(*_args, **_kwargs):
        return False

    monkeypatch.setattr("app.core.security.is_permitted", _deny)

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/v1/sync/active-pipelines",
                params={"year": 2025, "modules": "1,2"},
            )
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_active_pipelines_filters_per_module_by_decision(pg_dsn, monkeypatch):
    """Per-module sparse-passthrough deny — the security guard added in
    PR #1079 V1.

    The global gate (``backoffice.data_management.view``) passes; the
    per-module ``get_module_permission_decision`` denies module 1 and
    allows module 2.  The endpoint must drop module 1 from the response
    while keeping module 2 — proving the per-module filter actually
    runs and isn't accidentally short-circuited by the global gate.

    Without this test, a regression that inverts the
    ``decision.get("allow")`` check (e.g. typo, default, refactor) would
    be invisible to CI: ``pg_app``'s blanket allow-mock hides it, and
    the global-gate test above only exercises ``is_permitted``.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    pipeline_a = uuid4()
    pipeline_b = uuid4()
    async with Sf() as session:
        session.add(
            _make_active_pipeline_job(
                module_type_id=1, year=2025, pipeline_id=pipeline_a
            )
        )
        session.add(
            _make_active_pipeline_job(
                module_type_id=2, year=2025, pipeline_id=pipeline_b
            )
        )
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

    # Pass the global gate so the per-module filter is what gates the
    # response.
    async def _allow_global(*_args, **_kwargs):
        return True

    monkeypatch.setattr("app.core.security.is_permitted", _allow_global)

    # Per-module filter: deny module 1, allow module 2.
    async def _per_module_decision(_user, module_id, _action):
        return {"allow": int(module_id) != 1}

    monkeypatch.setattr(
        "app.api.v1.data_sync.get_module_permission_decision",
        _per_module_decision,
    )

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/v1/sync/active-pipelines",
                params={"year": 2025, "modules": "1,2"},
            )
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "1" not in body, (
        f"module 1 was denied per-module but appears in response: {body}"
    )
    assert body.get("2") == str(pipeline_b), (
        f"module 2 was allowed but missing or wrong in response: {body}"
    )
