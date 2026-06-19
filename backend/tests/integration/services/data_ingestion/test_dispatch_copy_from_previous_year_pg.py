"""Regression tests for the ``copy from previous year`` dispatch flow.

User-reported bug (Guilbert, 2026-05-21): clicking "Copy from previous
year" in the data-management dialog produced a 503 with
``{"detail": "Cannot connect to IngestionMethod.csv"}``.

Root cause: the frontend's ``copyFromPreviousYear`` flow sends
``config.source_job_id`` (not ``file_path``) on ``POST /sync/dispatch``.
The backend had no handler for ``source_job_id``: pydantic silently
dropped it (``SyncRequestConfig`` didn't declare the field), the CSV
provider saw ``file_path = None``, ``validate_connection`` returned
``False``, and the dispatch route raised a misleading 503 designed for
API-provider connectivity failures.

Fix: ``SyncRequestConfig`` declares ``source_job_id`` and the dispatch
route now resolves it via ``_resolve_source_job_to_file_path`` —
copies the source job's processed CSV into a fresh ``tmp/copy-*``
location and injects that as ``file_path``.  These tests pin the happy
path and the four validation branches that would silently mis-route
operator intent if dropped.

The tests do NOT exercise the downstream pipeline run — ``fire_and_forget``
is replaced with a no-op so we assert what the **dispatch endpoint
itself** decided, not what an in-flight CSV would do.  The existing
factor-reupload integration test covers the full pipeline run.

Requires Docker — see ``conftest.py``'s ``postgres_container``.
"""

from datetime import datetime, timezone
from pathlib import Path
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
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration

DISPATCH_URL = "/api/v1/sync/dispatch"
SOURCE_YEAR = 2025
TARGET_YEAR = 2026
MODULE_ID = int(ModuleTypeEnum.purchase)


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch, tmp_path):
    """Wire FastAPI to test PG, redirect files_store, bypass auth.

    Mirrors the proven setup in
    ``test_plan_310b_factor_reupload_endpoint_pg.py`` minus the runner
    plumbing — these tests assert the **dispatch endpoint's**
    behaviour, not the downstream pipeline, so we no-op
    ``fire_and_forget`` to avoid kicking off the actual chain (which
    would need the full 310B index install + SessionLocal patches).
    """
    psycopg_dsn = pg_dsn.replace("+asyncpg", "+psycopg")
    test_engine = create_async_engine(psycopg_dsn, future=True)
    Sf = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-COPY-FROM-PREV"
    fake_user.provider = UserProvider.DEFAULT
    # Stamped into the job's JSON ``meta.created_by``; must be serializable.
    fake_user.display_name = "Test User"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _allow(*_args, **_kwargs):
        return True

    # Patch where used (data_sync.py does ``from app.core.security
    # import is_permitted`` at import time, copying the reference).
    monkeypatch.setattr("app.core.security.is_permitted", _allow)
    monkeypatch.setattr("app.api.v1.data_sync.is_permitted", _allow)

    # Files store → tmp_path.  Disable Fernet so the CSV we write below
    # round-trips as plaintext (production encrypts at rest; out of
    # scope for this dispatch-routing test).
    settings = get_settings()
    monkeypatch.setattr(settings, "FILES_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "FILES_ENCRYPTION_KEY", "")
    monkeypatch.setattr(settings, "FILES_ENCRYPTION_SALT", "")

    # No-op the background dispatch: these tests assert the **endpoint's**
    # decisions (resolved file_path, new job's meta, HTTP code).  Letting
    # ``run_job`` actually fire would require the full 310B setup
    # (SessionLocal patches, partial unique indexes) and is covered by
    # the factor-reupload integration test.  ``close()`` the coroutine
    # so pytest doesn't log a "coroutine was never awaited" warning
    # (production ``fire_and_forget`` consumes it via ``asyncio.Task``).
    def _consume_coro(coro, *_args, **_kwargs):
        coro.close()
        return None

    monkeypatch.setattr("app.api.v1.data_sync.fire_and_forget", _consume_coro)

    yield {"factory": Sf, "tmp_path": tmp_path}

    app.dependency_overrides.clear()
    await test_engine.dispose()


async def _seed_year_configurations(Sf) -> None:
    """Both years need ``configuration_completed`` set or dispatch
    returns 409 before reaching the copy-resolution path.

    Source year (2025) carries no semantics for the resolver but
    pydantic-validating the request needs the target year's config to
    have completed provisioning.  Seeding both keeps the test free of
    incidental setup error surface.
    """
    async with Sf() as s:
        s.add_all(
            [
                YearConfiguration(
                    year=SOURCE_YEAR,
                    is_started=True,
                    config={},
                    configuration_completed=datetime.now(timezone.utc),
                ),
                YearConfiguration(
                    year=TARGET_YEAR,
                    is_started=True,
                    config={},
                    configuration_completed=datetime.now(timezone.utc),
                ),
            ]
        )
        await s.commit()


async def _seed_source_job(
    Sf,
    *,
    state: IngestionState = IngestionState.FINISHED,
    result: IngestionResult = IngestionResult.SUCCESS,
    target_type: TargetType = TargetType.FACTORS,
    module_type_id: int = MODULE_ID,
    processed_file_path: str | None = "processed/61/factors.csv",
) -> int:
    """Insert a candidate source job; caller controls the fields that
    drive the resolver's validation branches (state, target_type, …)."""
    meta: dict = {}
    if processed_file_path is not None:
        meta["processed_file_path"] = processed_file_path
    async with Sf() as s:
        job = DataIngestionJob(
            entity_type=EntityType.MODULE_PER_YEAR,
            module_type_id=module_type_id,
            year=SOURCE_YEAR,
            target_type=target_type,
            ingestion_method=IngestionMethod.csv,
            provider=UserProvider.DEFAULT,
            state=state,
            result=result,
            is_current=True,
            job_type="factor_ingest",
            meta=meta,
        )
        s.add(job)
        await s.commit()
        return job.id


def _write_processed_file(tmp_path: Path, *, content: str) -> None:
    """Materialise the ``processed/61/factors.csv`` the source job
    points at, so the resolver's ``files_store.get_file`` succeeds.

    The CSV content itself is opaque to the resolver — it just copies
    bytes — but it must be non-empty so ``UploadFile.size`` is truthful
    when the resolver re-writes it under ``tmp/copy-*``.
    """
    processed = tmp_path / "processed" / "61"
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "factors.csv").write_text(content)


def _dispatch_body(
    *,
    source_job_id: int,
    target_type: int = int(TargetType.FACTORS),
    module_type_id: int = MODULE_ID,
    year: int = TARGET_YEAR,
) -> dict:
    """The exact payload shape the frontend's
    ``copyFromPreviousYear`` sends — keep the literal here so a
    silent contract drift between frontend and backend trips this
    test."""
    return {
        "ingestion_method": int(IngestionMethod.csv),
        "target_type": target_type,
        "year": year,
        "filters": {},
        "config": {
            "source_job_id": source_job_id,
            "module_type_id": module_type_id,
        },
    }


@pytest.mark.asyncio
async def test_dispatch_copy_resolves_source_to_tmp_file_path(pg_app):
    """Happy path: source job FINISHED+SUCCESS with a processed file →
    new job created with ``file_path`` under ``tmp/copy-*`` and
    ``copied_from_job_id`` in the config provenance trail."""
    Sf = pg_app["factory"]
    await _seed_year_configurations(Sf)
    _write_processed_file(pg_app["tmp_path"], content="col1,col2\n1,2\n")
    source_id = await _seed_source_job(Sf)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            DISPATCH_URL, json=_dispatch_body(source_job_id=source_id)
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    new_job_id = body["job_id"]
    assert new_job_id != source_id

    async with Sf() as s:
        new_job = await s.get(DataIngestionJob, new_job_id)
        assert new_job is not None
        # The dispatch endpoint stamps ``config`` inside ``meta`` (via
        # the provider's ``create_job``).  Verify both halves of the
        # copy-resolution contract: the resolved ``file_path`` points
        # into ``tmp/copy-*`` AND the provenance trail records the
        # source job_id so support can answer "which year's CSV was
        # this?".
        cfg = (new_job.meta or {}).get("config", {})
        assert cfg.get("file_path", "").startswith("tmp/copy-"), cfg
        assert cfg.get("file_path", "").endswith("/factors.csv"), cfg
        assert cfg.get("copied_from_job_id") == source_id, cfg

    # Resolver actually wrote a copy of the source CSV at the new path.
    staged = pg_app["tmp_path"] / cfg["file_path"]
    assert staged.is_file(), f"resolver did not stage {cfg['file_path']}"


@pytest.mark.asyncio
async def test_dispatch_copy_returns_404_when_source_job_missing(pg_app):
    """Unknown ``source_job_id`` → 404, not the misleading 503."""
    Sf = pg_app["factory"]
    await _seed_year_configurations(Sf)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            DISPATCH_URL, json=_dispatch_body(source_job_id=999_999)
        )

    assert resp.status_code == 404, resp.text
    assert "999999" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_dispatch_copy_rejects_non_terminal_source(pg_app):
    """RUNNING (or otherwise non-FINISHED+SUCCESS) source → 422.

    The processed file path is only stamped at the end of a successful
    ingest; in-flight or failed jobs have no usable file to copy.  The
    422 surface lets the frontend show "this run hasn't finished yet"
    instead of pretending the copy worked then breaking mid-chain.
    """
    Sf = pg_app["factory"]
    await _seed_year_configurations(Sf)
    _write_processed_file(pg_app["tmp_path"], content="col1\n1\n")
    source_id = await _seed_source_job(
        Sf,
        state=IngestionState.RUNNING,
        result=IngestionResult.SUCCESS,
        processed_file_path=None,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            DISPATCH_URL, json=_dispatch_body(source_job_id=source_id)
        )

    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_dispatch_copy_rejects_target_type_mismatch(pg_app):
    """Source DATA_ENTRIES → request FACTORS → 400.

    Pins the validation: copying a DATA_ENTRIES CSV under a FACTORS
    dispatch would silently parse rows with the wrong handler and
    produce mojibake stats.  The 400 stops the misroute before any
    rows hit the DB.
    """
    Sf = pg_app["factory"]
    await _seed_year_configurations(Sf)
    _write_processed_file(pg_app["tmp_path"], content="col1\n1\n")
    source_id = await _seed_source_job(Sf, target_type=TargetType.DATA_ENTRIES)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            DISPATCH_URL,
            json=_dispatch_body(
                source_job_id=source_id, target_type=int(TargetType.FACTORS)
            ),
        )

    assert resp.status_code == 400, resp.text
    assert "target_type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_dispatch_copy_rejects_module_type_mismatch(pg_app):
    """Source for module=equipment → request module=headcount → 400.

    Defensive against the operator picking a job from the wrong
    module in the previous-year dropdown — same misroute risk as
    the target_type mismatch above.
    """
    Sf = pg_app["factory"]
    await _seed_year_configurations(Sf)
    _write_processed_file(pg_app["tmp_path"], content="col1\n1\n")
    source_id = await _seed_source_job(Sf, module_type_id=int(ModuleTypeEnum.purchase))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            DISPATCH_URL,
            json=_dispatch_body(
                source_job_id=source_id,
                module_type_id=int(ModuleTypeEnum.headcount),
            ),
        )

    assert resp.status_code == 400, resp.text
    assert "module_type_id" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_dispatch_copy_rejects_source_without_processed_file_path(pg_app):
    """FINISHED+SUCCESS source that somehow has no ``processed_file_path``
    in its meta → 422.

    Defensive: API providers never stamp this key, and a CSV provider
    that fails between processed/ move and meta-flush could leave
    a SUCCESS row with no path either.  Surface clearly instead of
    crashing later in the file-copy.
    """
    Sf = pg_app["factory"]
    await _seed_year_configurations(Sf)
    source_id = await _seed_source_job(Sf, processed_file_path=None)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            DISPATCH_URL, json=_dispatch_body(source_job_id=source_id)
        )

    assert resp.status_code == 422, resp.text
    assert "processed file" in resp.json()["detail"]
