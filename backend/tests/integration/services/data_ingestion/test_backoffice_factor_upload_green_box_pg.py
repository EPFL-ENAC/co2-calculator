"""Integration tests for the backoffice factor-upload pipeline (issue
#1403 checklist, slice (b) — backend common-module-behavior):

- Uploading a factor file leads to a job with no error status (the
  Configurator's "green box" condition) — driven at the API level
  (``POST /files/temp-upload`` + ``POST /sync/dispatch``), not the UI.
- The validation pipeline correctly *dispatches* a bad row to a recorded
  row-error without aborting the whole batch (spot-check of one concrete,
  already-implemented field-level rule — not a re-test of every DTO;
  field-level validation itself is covered by
  ``tests/unit/services/data_ingestion/csv_providers/``).

Both tests drive the real ``ModulePerYearFactorCSVProvider`` against the
committed CI-safe fixture ``tests/fixtures/csv/purchases_common_factors_
smoke.csv`` (module-level "common factor" upload for Purchase, module_type
5). This lives under ``services/data_ingestion/`` (not the new
``backoffice/`` package) and requires real Postgres — ``FactorRepository.
upsert_factors`` issues a Postgres-only ``ON CONFLICT ... (classification::
text)`` upsert that SQLite cannot parse, so every existing test that
exercises real factor upsert already lives here as a ``_pg`` suite; this
mirrors that established placement rather than fighting it.

Setup mirrors ``test_plan_310b_factor_reupload_endpoint_pg.py``: real HTTP
dispatch, ``SessionLocal`` monkeypatched so the background job runs
against the test Postgres, and the ``+psycopg`` driver (not ``+asyncpg``)
for the app-facing engine — asyncpg is strict about tz-aware datetimes on
a tz-naive column in ``audit_documents.changed_at`` (a latent, unrelated
model bug production's psycopg driver silently coerces around; out of
scope here, see that file's comment for the full story).
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
from app.main import app
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration
from app.services.year_config_service import generate_default_year_config

from .conftest import csv_fixture_path

YEAR = 2025
POLL_TIMEOUT_SECONDS = 15.0
POLL_INTERVAL_SECONDS = 0.1


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch, tmp_path):
    """Wire the FastAPI app to the test Postgres + bypass auth + redirect
    file storage to ``tmp_path``. See module docstring for the
    ``+psycopg`` driver rationale."""
    psycopg_dsn = pg_dsn.replace("+asyncpg", "+psycopg")
    engine = create_async_engine(psycopg_dsn, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "backoffice-admin@example.com"
    fake_user.display_name = "Backoffice Admin"
    fake_user.institutional_id = "99999"
    fake_user.provider = UserProvider.DEFAULT
    # ``/files/temp-upload`` gates on this directly (not the mockable
    # ``is_permitted`` OPA call).
    fake_user.calculate_permissions.return_value = {
        "backoffice.configuration": ["view", "edit"]
    }

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user

    async def always_allowed(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr("app.api.v1.data_sync.is_permitted", always_allowed)

    monkeypatch.setattr(
        "app.core.config.get_settings.cache_clear", lambda: None, raising=False
    )
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "FILES_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "FILES_ENCRYPTION_KEY", "")
    monkeypatch.setattr(settings, "FILES_ENCRYPTION_SALT", "")

    # Plan 310-C: every job_type funnels through app.tasks.runner, which
    # opens its own sessions via the bare ``SessionLocal`` name imported
    # at module load — rebind where it's used, not where it's defined.
    monkeypatch.setattr("app.tasks.runner.SessionLocal", factory)
    monkeypatch.setattr("app.tasks.emission_recalculation_tasks.SessionLocal", factory)

    async with factory() as session:
        session.add(
            YearConfiguration(
                year=YEAR,
                provider=UserProvider.DEFAULT,
                is_started=False,
                configuration_completed=datetime.now(timezone.utc),
                config=generate_default_year_config(),
            )
        )
        await session.commit()

    yield {"factory": factory, "dsn": psycopg_dsn}

    app.dependency_overrides.clear()
    await engine.dispose()


async def _wait_for_job(
    factory, job_id: int, *, timeout: float = POLL_TIMEOUT_SECONDS
) -> DataIngestionJob:
    import asyncio
    import time

    deadline = time.monotonic() + timeout
    last_state = None
    while time.monotonic() < deadline:
        async with factory() as s:
            row = (
                await s.execute(
                    select(DataIngestionJob).where(col(DataIngestionJob.id) == job_id)
                )
            ).scalar_one()
            last_state = row.state
            if row.state == IngestionState.FINISHED:
                return row
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(
        f"Job {job_id} did not reach FINISHED within {timeout}s "
        f"(last state seen: {last_state})"
    )


async def _upload_and_dispatch(
    client, *, csv_bytes: bytes, filename: str, tmp_path: Path
) -> int:
    """Write the CSV straight into the (patched) storage root and dispatch.

    Mirrors ``test_plan_310b_factor_reupload_endpoint_pg.py``: the real
    ``/files/temp-upload`` endpoint holds a MODULE-LEVEL ``files_store``
    singleton built at import time (``app/api/v1/files.py``), so
    patching ``settings.FILES_STORAGE_PATH`` after import never reaches
    it — only the factor provider's lazily-constructed ``files_store``
    (built per-request from live settings) sees the patched path. Writing
    the file directly sidesteps that singleton mismatch; ``/sync/dispatch``
    is still the real API surface under test.
    """
    folder = tmp_path / "tmp" / "green_box"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_bytes(csv_bytes)
    file_path = f"tmp/green_box/{filename}"

    dispatch = await client.post(
        "/v1/sync/dispatch",
        json={
            "ingestion_method": IngestionMethod.csv.value,
            "target_type": TargetType.FACTORS.value,
            "year": YEAR,
            "file_path": file_path,
            "config": {"module_type_id": ModuleTypeEnum.purchase.value},
        },
    )
    assert dispatch.status_code == 200, dispatch.text
    body = dispatch.json()
    assert body["state"] == IngestionState.NOT_STARTED.value, (
        "dispatch itself must not report an error state"
    )
    return body["job_id"]


@pytest.mark.asyncio
async def test_factor_csv_upload_dispatches_and_finishes_without_error(
    pg_app, tmp_path
):
    """Green-box condition: a valid factor CSV, uploaded and dispatched
    through the real API, runs through the real ``ModulePerYearFactorCSV
    Provider`` and reaches FINISHED with a non-ERROR result."""
    factory = pg_app["factory"]
    csv_path: Path = csv_fixture_path("purchases_common", "factors")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        job_id = await _upload_and_dispatch(
            client,
            csv_bytes=csv_path.read_bytes(),
            filename="purchases_common_factors_smoke.csv",
            tmp_path=tmp_path,
        )

    job = await _wait_for_job(factory, job_id)

    assert job.job_type == "factor_ingest"
    assert job.target_type == TargetType.FACTORS
    assert job.result == IngestionResult.SUCCESS, job.status_message

    # The planner's per-CHF averages are derived from this upload, in its own
    # transaction — a plan priced against them can never lag the Calculator.
    async with factory() as s:
        derived = (
            (
                await s.execute(
                    select(Factor).where(
                        col(Factor.data_entry_type_id)
                        == DataEntryTypeEnum.planner_purchase.value,
                        col(Factor.year) == YEAR,
                    )
                )
            )
            .scalars()
            .all()
        )
    assert {f.classification["purchase_category"] for f in derived} == {
        "scientific_equipment",
        "it_equipment",
        "consumable_accessories",
        "biological_chemical_gaseous_product",
        "services",
    }, "one derived factor per category the CSV priced"
    assert all(f.values["ef_kg_co2eq_per_eur"] > 0 for f in derived)

    async with factory() as s:
        budget = (
            (
                await s.execute(
                    select(Factor).where(
                        col(Factor.data_entry_type_id)
                        == DataEntryTypeEnum.planner_purchase_budget.value
                    )
                )
            )
            .scalars()
            .one()
        )
    # The global budget averages the category means, so it is not pulled by
    # whichever category the CSV happens to carry the most codes for.
    assert budget.values["ef_kg_co2eq_per_eur"] == pytest.approx(
        sum(f.values["ef_kg_co2eq_per_eur"] for f in derived) / len(derived), rel=1e-4
    )


@pytest.mark.asyncio
async def test_factor_csv_upload_flags_invalid_category_without_aborting_batch(
    pg_app, tmp_path
):
    """Spot-check of one concrete, already-implemented validation rule:
    ``purchase_category`` must match a ``DataEntryTypeEnum`` member name
    exactly (``_resolve_data_entry_type`` in ``base_factor_csv_provider.
    py``). One bad row alongside good ones must be recorded as a row
    error and skipped — not silently accepted, and not fatal to the rest
    of the batch — pinning that the pipeline *dispatches* validation
    failures correctly rather than either ignoring or over-rejecting them."""
    factory = pg_app["factory"]
    csv_path: Path = csv_fixture_path("purchases_common", "factors")
    lines = csv_path.read_text().splitlines()
    header, valid_rows = lines[0], lines[1:]
    bad_row = "eur,not_a_real_category,99999999,Bogus,ZZ,0.5"
    csv_bytes = "\n".join([header, *valid_rows, bad_row]).encode()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        job_id = await _upload_and_dispatch(
            client,
            csv_bytes=csv_bytes,
            filename="purchases_common_factors_with_bad_row.csv",
            tmp_path=tmp_path,
        )

    job = await _wait_for_job(factory, job_id)

    # Partial success: the good rows still upserted, so the pipeline
    # downgrades to WARNING rather than failing the whole file.
    assert job.result == IngestionResult.WARNING, job.status_message
    stats = (job.meta or {}).get("stats", {})
    assert stats.get("row_errors_count") == 1
    row_errors = stats.get("row_errors", [])
    assert any("not_a_real_category" in e.get("reason", "") for e in row_errors), (
        row_errors
    )
