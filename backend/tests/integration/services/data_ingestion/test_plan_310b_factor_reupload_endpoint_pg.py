"""End-to-end PG regression test for the #310B fire_and_forget cancellation bug.

The bug: ``data_sync.py`` formerly handed the **sync** wrapper
``run_ingestion`` to ``background_tasks.add_task``.  FastAPI runs sync
background tasks in an anyio worker thread; ``run_ingestion`` did
``asyncio.run(run_sync_task(...))`` which built a throwaway event loop
in that thread.  Inside, ``_enqueue_stale_recalculations`` called
``fire_and_forget(run_recalculation_task(...))`` — and the recalc Task
was bound to the throwaway loop.  When ``asyncio.run`` exited and closed
its loop, the recalc Task was cancelled silently, leaving the child
``DataIngestionJob`` row stuck in ``state=RUNNING`` with empty
``status_message``.

Why no existing test caught it: every other test either calls internal
functions directly on pytest's long-lived loop (which never reproduces
the cancellation), or hits HTTP with the spawned task patched to a
noop (so it never actually runs).  This test is the missing one — full
chain ``HTTP → BackgroundTasks → run_sync_task → fire_and_forget →
run_recalculation_task → DataEntryEmission updated``.

Setup mirrors:
- ``test_sync_units_endpoint_pg.py`` for the ``httpx.AsyncClient +
  ASGITransport`` + ``app.dependency_overrides`` rig
- ``test_plan_310b_emission_change_pg.py`` for the seed graph (Unit →
  CarbonReport → CarbonReportModule → Factor → DataEntry → emission)
- ``test_plan_310b_recalc_empty_entries_pg.py`` for the SessionLocal
  monkeypatch trick that points the background-task code at the test
  Postgres container

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import asyncio
import time
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
import app.core.security as security_module
from app.main import app
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.year_configuration import YearConfiguration
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService

POLL_TIMEOUT_SECONDS = 15.0
POLL_INTERVAL_SECONDS = 0.1


@pytest_asyncio.fixture
async def pg_app(pg_dsn_with_310b, monkeypatch, tmp_path):
    """Wire the FastAPI app to the test Postgres + bypass auth + redirect
    file storage to ``tmp_path``.

    Three monkeypatches matter:
    1. ``settings.FILES_STORAGE_PATH`` → tmp_path.  ``LocalFilesStore``
       reads this lazily from ``make_files_store()``, which the factor
       provider calls in its __init__.  Both the request-handler-side
       provider and the run_sync_task-side provider pick up the new
       path because we set this before the request is fired.
    2. ``app.tasks.ingestion_tasks.SessionLocal`` → test sessionmaker.
       ``run_sync_task`` opens its own job/data sessions via
       ``app.db.SessionLocal``; that ``from app.db import SessionLocal``
       happens at import time, so we have to rebind the name where it's
       used, not at the source.
    3. ``app.tasks.emission_recalculation_tasks.SessionLocal`` →
       same reason, for the recalc child task.

    The ``app.dependency_overrides`` for ``get_db`` covers the request
    handler side; the SessionLocal monkeypatches cover the background
    task side.  Without both, the background task would talk to the
    production DB while the request handler talks to the test DB.

    Depends on ``pg_dsn_with_310b`` (in conftest) so the partial unique
    indexes Plan 310B's migration adds are present — ``upsert_factors``
    needs them to bind ``ON CONFLICT``.
    """
    # ``pg_dsn_with_310b`` returns a ``postgresql+asyncpg`` URL.  asyncpg
    # is strict about tz-aware vs tz-naive datetimes, which trips an
    # unrelated latent issue in app.models.audit (``changed_at`` defaults
    # to naive datetime.utcnow but audit_service writes tz-aware).
    # Production uses ``postgresql+psycopg`` which silently coerces.  Use
    # the same driver here so the test isn't tripped by a model-side bug
    # that's out of scope for #310B.
    psycopg_dsn = pg_dsn_with_310b.replace("+asyncpg", "+psycopg")
    test_engine = create_async_engine(psycopg_dsn, future=True)
    Sf = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-310B"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _allow(*_args, **_kwargs):
        return True

    # Patch where the name is *used*, not where it's defined: data_sync.py
    # does ``from app.core.security import is_permitted`` at import time,
    # which copies the reference into its own namespace.  Patching
    # ``app.core.security.is_permitted`` alone leaves data_sync's copy
    # bound to the original (denying-by-default) implementation.
    monkeypatch.setattr("app.core.security.is_permitted", _allow)
    monkeypatch.setattr("app.api.v1.data_sync.is_permitted", _allow)

    # Redirect file storage to tmp_path so the factor CSV we write below
    # is what the LocalFilesStore reads.
    monkeypatch.setattr(
        "app.core.config.get_settings.cache_clear", lambda: None, raising=False
    )
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "FILES_STORAGE_PATH", str(tmp_path))
    # Disable LocalFilesStore Fernet encryption so the plaintext CSV
    # we write below isn't treated as ciphertext on read.  In production
    # FILES_ENCRYPTION_KEY is set and files are encrypted at rest;
    # exercising that path is out of scope for the recalc-fan-out test.
    monkeypatch.setattr(settings, "FILES_ENCRYPTION_KEY", "")
    monkeypatch.setattr(settings, "FILES_ENCRYPTION_SALT", "")

    # Point the runner's SessionLocal at the test PG.  Plan 310-C
    # cutover: every job_type now funnels through ``app.tasks.runner``,
    # which opens its own sessions via the bare ``SessionLocal`` name.
    # Patching here covers both the parent factor_ingest run AND the
    # chained emission_recalc child (same runner, same module).
    monkeypatch.setattr("app.tasks.runner.SessionLocal", Sf)

    yield {"factory": Sf, "dsn": pg_dsn_with_310b, "tmp_path": tmp_path}

    app.dependency_overrides.clear()
    await test_engine.dispose()


async def _wait_for_job(
    Sf, job_id: int, *, timeout: float = POLL_TIMEOUT_SECONDS
) -> DataIngestionJob:
    """Plain ``while ... await asyncio.sleep`` polling.  Returns the row
    once it reaches a terminal state, or raises ``AssertionError`` on
    timeout — leaves the row state in the message so failures are
    diagnosable from the assertion alone."""
    deadline = time.monotonic() + timeout
    last_state = None
    while time.monotonic() < deadline:
        async with Sf() as s:
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
        f"(last state seen: {last_state}). "
        "If this asserts, the recalc Task was likely cancelled — re-check "
        "data_sync.py for any sync wrapper passed to background_tasks.add_task."
    )


async def _wait_for_child_recalc_job(
    Sf, parent_job_id: int, *, timeout: float = POLL_TIMEOUT_SECONDS
) -> DataIngestionJob:
    """Find the recalc child job spawned by the factor_ingest handler's
    fan-out.

    Phase 5B (#1236) retired ``meta.parent_job_id`` — children are now
    tied to their parent only by the shared ``pipeline_id``.  Look the
    parent up by ``parent_job_id`` to read its ``pipeline_id``, then
    match the emission_recalc child by that.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        async with Sf() as s:
            parent = await s.get(DataIngestionJob, parent_job_id)
            if parent is None or parent.pipeline_id is None:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue
            rows = (
                (
                    await s.execute(
                        select(DataIngestionJob).where(
                            col(DataIngestionJob.job_type) == "emission_recalc",
                            col(DataIngestionJob.pipeline_id) == parent.pipeline_id,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                if row.state == IngestionState.FINISHED:
                    return row
                # Found the row but not done yet — fall through to the sleep
                # so we re-poll instead of giving up.
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(
        f"Child recalc job for parent={parent_job_id} did not reach FINISHED "
        f"within {timeout}s.  This is the exact symptom of the #310B bug — "
        "check that data_sync.py uses async fns for background_tasks.add_task."
    )


@pytest.mark.asyncio
async def test_factor_reupload_endpoint_recomputes_emission_via_recalc_task(
    pg_app,
):
    """Full HTTP path → BackgroundTasks → run_sync_task → fire_and_forget
    → run_recalculation_task → DataEntryEmission updated.

    Seeds Factor v1 (ef=0.1) + DataEntry + initial emission, then POSTs
    a factor v2 CSV (ef=0.2) to ``/v1/sync/dispatch``.  Polls both the
    parent FACTORS job and the spawned child recalc job to FINISHED,
    then re-reads emissions on a separate engine and asserts the value
    doubled.
    """
    Sf = pg_app["factory"]
    pg_dsn = pg_app["dsn"]
    tmp_path: Path = pg_app["tmp_path"]

    # ── 1. Seed the carbon-report graph + factor v1 + data entry ───────
    # ``/v1/sync/dispatch`` (#1234-followup) refuses uploads for a year
    # whose ``unit_sync`` pipeline hasn't finished SUCCESS — gated by
    # ``year_configuration.configuration_completed``.  This test stages
    # the post-provisioned graph by hand (CarbonReports / CRMs already
    # exist below), so we stamp the marker explicitly to mirror what
    # ``unit_sync_handler`` would have written on a real run.
    async with Sf() as s:
        s.add(
            YearConfiguration(
                year=2025,
                is_started=True,
                configuration_completed=datetime.now(timezone.utc),
            )
        )
        await s.commit()

    async with Sf() as s:
        unit = Unit(
            institutional_code="TEST-310B",
            institutional_id="TEST-UNIT-310B",
            name="Test Unit 310B",
            level=1,
        )
        s.add(unit)
        await s.commit()

        report = CarbonReport(year=2025, unit_id=unit.id)
        s.add(report)
        await s.commit()

        module = CarbonReportModule(
            carbon_report_id=report.id,
            module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
        )
        s.add(module)
        await s.commit()

        # ``year`` is stored on the dedicated column only — Plan 310B
        # stops duplicating it inside ``classification``, so the seed
        # matches the canonical year-less shape that re-uploads now write.
        factor = Factor(
            emission_type_id=EmissionType.equipment__it.value,
            data_entry_type_id=DataEntryTypeEnum.it.value,
            classification={
                "equipment_class": "Laptop",
                "sub_class": "Standard",
            },
            values={
                "active_power_w": 100.0,
                "standby_power_w": 10.0,
                "ef_kg_co2eq_per_kwh": 0.1,
            },
            year=2025,
        )
        s.add(factor)
        await s.commit()
        factor_id = factor.id

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.it.value,
            carbon_report_module_id=module.id,
            data={
                "primary_factor_id": factor_id,
                "equipment_class": "Laptop",
                "sub_class": "Standard",
                "active_usage_hours_per_week": 40.0,
                "standby_usage_hours_per_week": 128.0,
                "name": "Test Laptop 310B",
            },
        )
        s.add(entry)
        await s.commit()
        entry_id = entry.id

    # ── 2. Compute initial emission so the recalc has something to do ──
    async with Sf() as s:
        e = (
            await s.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
        ).scalar_one()
        await DataEntryEmissionService(s).upsert_by_data_entry(
            DataEntryResponse.model_validate(e)
        )
        await s.commit()

    async with Sf() as s:
        initial_total = sum(
            (r.kg_co2eq or 0.0)
            for r in (
                (
                    await s.execute(
                        select(DataEntryEmission).where(
                            col(DataEntryEmission.data_entry_id) == entry_id
                        )
                    )
                )
                .scalars()
                .all()
            )
        )
    assert initial_total > 0, (
        "initial emission should be non-zero before the test exercises recalc"
    )

    # ── 3. Write factor v2 CSV (ef doubled) to the patched files dir ───
    csv_dir = tmp_path / "tmp" / "test_310b"
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / "factor_v2.csv"
    csv_path.write_text(
        "equipment_category,equipment_class,sub_class,active_power_w,"
        "standby_power_w,active_usage_hours_per_week,"
        "standby_usage_hours_per_week,ef_kg_co2eq_per_kwh\n"
        "it,Laptop,Standard,100,10,40,128,0.2\n"
    )
    csv_relative = "tmp/test_310b/factor_v2.csv"

    # ── 4. POST /v1/sync/dispatch ──────────────────────────────────────
    # Single-type variant: parent job carries data_entry_type_id=it, so
    # _enqueue_stale_recalculations enters the ELSE branch and queries
    # get_recalculation_status_by_year, which returns a row needing
    # recalculation (no prior recalc job + a fresh FACTORS job).
    sync_request = {
        "ingestion_method": IngestionMethod.csv.value,
        "target_type": TargetType.FACTORS.value,
        "year": 2025,
        "file_path": csv_relative,
        "config": {
            "module_type_id": ModuleTypeEnum.equipment_electric_consumption.value,
            "data_entry_type_id": DataEntryTypeEnum.it.value,
        },
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/v1/sync/dispatch", json=sync_request)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    parent_job_id = body["job_id"]
    assert parent_job_id and parent_job_id > 0

    # ── 5. Poll parent factor job → FINISHED + SUCCESS ─────────────────
    parent_row = await _wait_for_job(Sf, parent_job_id)
    assert parent_row.result == IngestionResult.SUCCESS, (
        f"parent factor job did not succeed: state={parent_row.state}, "
        f"result={parent_row.result}, status_message={parent_row.status_message!r}"
    )

    # ── 6. Poll child recalc job → FINISHED ────────────────────────────
    # If this asserts, the recalc Task was cancelled.  That's the bug.
    child_row = await _wait_for_child_recalc_job(Sf, parent_job_id)
    assert child_row.result == IngestionResult.SUCCESS, (
        f"child recalc job did not succeed: state={child_row.state}, "
        f"result={child_row.result}, status_message={child_row.status_message!r}"
    )

    # ── 7. Verify on a SEPARATE engine — emission doubled ──────────────
    psycopg_dsn = pg_dsn.replace("+asyncpg", "+psycopg")
    verify_engine = create_async_engine(psycopg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            new_total = sum(
                (r.kg_co2eq or 0.0)
                for r in (
                    (
                        await vs.execute(
                            select(DataEntryEmission).where(
                                col(DataEntryEmission.data_entry_id) == entry_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            )
    finally:
        await verify_engine.dispose()

    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3), (
        "factor reupload should have doubled the emission "
        f"(initial={initial_total}, new={new_total}).  If the values are "
        "equal, the recalc Task was scheduled but never ran — i.e. the "
        "#310B cancellation bug has been reintroduced."
    )
