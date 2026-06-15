"""Regression tests for the seed-stub-job helper (#1080 sprint-9).

User-reported: ``seed_generic_factors.py`` /
``seed_generic_data_entries.py`` insert factor / data-entry rows
directly, but the data-management page reads ``DataIngestionJob``
rows to render the per-card upload history — so seeded data was
invisible in the UI.

``app.seed._stub_jobs.create_seed_stub_job`` plants a FINISHED +
SUCCESS row matching what a real dispatch + provider would have
written.  These tests pin the shape so the cards' filename /
rows-imported / timestamp display lights up consistently.

Requires Docker — see ``conftest.py``'s ``postgres_container``.
"""

from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import ModuleTypeEnum
from app.seed._stub_jobs import create_seed_stub_job


@pytest_asyncio.fixture
async def Sf(pg_dsn):
    """Async sessionmaker against the test PG."""
    engine = create_async_engine(pg_dsn.replace("+asyncpg", "+psycopg"), future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_stub_job_has_terminal_state_for_card_display(Sf):
    """Stub job MUST be FINISHED + SUCCESS so the card shows
    "✓ filename" not the in-flight spinner.  Also pins ``is_current``
    so the latest-job picker honors it as the active history entry.
    """
    async with Sf() as s:
        job_id = await create_seed_stub_job(
            s,
            module_type_id=int(ModuleTypeEnum.headcount),
            data_entry_type_id=1,
            year=2025,
            target_type=TargetType.FACTORS,
            job_type="factor_ingest",
            file_path=Path("/some/seed/headcount_member_factors.csv"),
            rows_processed=42,
            rows_skipped=3,
        )
        await s.commit()

    async with Sf() as s:
        job = await s.get(DataIngestionJob, job_id)
        assert job is not None
        assert job.state == IngestionState.FINISHED
        assert job.result == IngestionResult.SUCCESS
        assert job.is_current is True
        assert job.ingestion_method == IngestionMethod.csv
        assert job.target_type == TargetType.FACTORS
        assert job.job_type == "factor_ingest"
        assert job.module_type_id == int(ModuleTypeEnum.headcount)
        assert job.data_entry_type_id == 1
        assert job.year == 2025
        assert job.status_message == "Seeded"
        assert job.started_at is not None
        assert job.finished_at is not None


@pytest.mark.asyncio
async def test_stub_meta_carries_card_display_fields(Sf):
    """Card-display contract: ``meta`` MUST carry ``file_path``,
    ``rows_processed`` and ``timestamp`` — those are the keys the
    frontend's ``getJobInfo`` reads to render "✓ <filename> · N rows
    imported · DD.MM.YYYY".  Also pins the ``seeded=True`` marker
    so operators can query "what came from the seed".
    """
    async with Sf() as s:
        job_id = await create_seed_stub_job(
            s,
            module_type_id=int(ModuleTypeEnum.purchase),
            data_entry_type_id=None,  # multi-DET — common factor
            year=2025,
            target_type=TargetType.FACTORS,
            job_type="factor_ingest",
            file_path=Path("/repo/seed_data/purchases_common_factors.csv"),
            rows_processed=1234,
            rows_skipped=0,
        )
        await s.commit()

    async with Sf() as s:
        job = await s.get(DataIngestionJob, job_id)
        assert job is not None
        meta = job.meta or {}
        assert meta.get("seeded") is True
        assert meta.get("rows_processed") == 1234
        assert meta.get("rows_skipped") == 0
        # File path: basename preserved, ``seed/`` prefix marks the
        # synthetic origin (real uploads use ``tmp/<ts>/<name>``).
        assert meta.get("file_path") == "seed/purchases_common_factors.csv"
        # Timestamp parseable as ISO8601 — the card passes it to
        # ``new Date(...)`` which would NaN-out on a bad string.
        ts = meta.get("timestamp")
        assert isinstance(ts, str)
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None  # tz-aware so frontend renders local


@pytest.mark.asyncio
async def test_stub_orphan_no_pipeline_id(Sf):
    """Seeded stubs deliberately carry no ``pipeline_id`` — seeds
    bypass the dispatch chain and shouldn't pretend to belong to
    one.  Pipeline-ops console renders them as orphans (``(no
    pipeline)`` tag), which is the honest signal.
    """
    async with Sf() as s:
        job_id = await create_seed_stub_job(
            s,
            module_type_id=int(ModuleTypeEnum.equipment),
            data_entry_type_id=None,
            year=2025,
            target_type=TargetType.DATA_ENTRIES,
            job_type="csv_ingest",
            file_path=Path("/repo/seed_data/equipments_data.csv"),
            rows_processed=10,
        )
        await s.commit()

    async with Sf() as s:
        job = await s.get(DataIngestionJob, job_id)
        assert job is not None
        assert job.pipeline_id is None, (
            f"seed stubs must be orphan (no pipeline_id) — got {job.pipeline_id!r}. "
            "A non-null pipeline_id would either FK-violate against the empty "
            "``pipelines`` table or invent a fake chain that downstream readers "
            "(orphan-aggregation sweep, pipeline-ops console) would try to "
            "reconcile."
        )
