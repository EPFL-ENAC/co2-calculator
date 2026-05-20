"""Regression: every ``data_ingestion_jobs`` write that carries a
``pipeline_id`` MUST be preceded by an ``ensure_pipeline_exists`` call
on the same session (#1236 Phase 2 FK enforcement).

History — bugs this test guards against:

1.  ``app/api/v1/year_configuration.py:create_year_configuration``
    shipped with no ``ensure_pipeline_exists`` call.  On stage the
    Phase-2 FK rejected the INSERT with
    ``ForeignKeyViolation: ... fk_data_ingestion_jobs_pipeline_id``.

2.  Two ``data_sync.py`` sites
    (``recalculate-emissions``, ``recalculate-module-emissions``)
    called ``ensure_pipeline_exists`` *after* ``create_ingestion_job``
    — but ``create_ingestion_job`` flushes, so the FK fired before the
    parent row was inserted.

3.  ``data_sync._stamp_job_type_and_meta`` and ``_chain.chain_job``
    assigned ``row.pipeline_id = X`` *before* calling
    ``ensure_pipeline_exists``.  The SELECT inside
    ``ensure_pipeline_exists`` triggers SQLAlchemy's autoflush, which
    writes an UPDATE that sets ``pipeline_id`` while ``pipelines`` is
    still empty → FK violation.  This shape is sneakier than (1)/(2):
    no explicit flush call, the autoflush is implicit.

All three shapes pre-Phase-2 (when there was no FK) wrote a
``data_ingestion_jobs`` row with a ``pipeline_id`` that pointed at
nothing in ``pipelines``, leaving the join unreliable.  The test
exercises the FK directly so any regression of any shape fails
loudly.

SQLite defaults to FKs *off*; we enable the PRAGMA on the test engine
so the constraint actually triggers — without it this test would
pass even with the bug back in place.
"""

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider
from app.repositories.data_ingestion import DataIngestionRepository


@pytest_asyncio.fixture
async def fk_db_session():
    """SQLite engine with FK enforcement turned on for THIS test.

    The default fixture (``conftest.db_session``) doesn't enable
    ``PRAGMA foreign_keys=ON`` so the Phase-2 FK is inert there — fine
    for the existing scope/grouping tests, but useless for catching
    FK-ordering regressions.  This per-test engine enables it via the
    documented sqlalchemy listener pattern.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, _):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


def _job_with_pipeline(pipeline_id):
    """Same shape the four mint sites build (sanitised for the test)."""
    return DataIngestionJob(
        job_type="unit_sync",
        module_type_id=None,
        data_entry_type_id=None,
        year=2026,
        ingestion_method=IngestionMethod.api,
        target_type=TargetType.REFERENCE_DATA,
        entity_type=EntityType.GLOBAL_PER_YEAR,
        provider=UserProvider.DEFAULT,
        state=IngestionState.NOT_STARTED,
        pipeline_id=pipeline_id,
        meta={"config": {"target_year": 2026}},
    )


@pytest.mark.asyncio
async def test_create_ingestion_job_without_ensure_pipeline_raises(
    fk_db_session: AsyncSession,
):
    """Negative control: skipping ``ensure_pipeline_exists`` triggers
    the FK.  Without this, the positive test below could pass for the
    wrong reason (e.g. FK enforcement not actually on).
    """
    from uuid import uuid4

    pid = uuid4()
    repo = DataIngestionRepository(fk_db_session)

    with pytest.raises(IntegrityError):
        # No ensure_pipeline_exists — FK should reject the flush.
        await repo.create_ingestion_job(_job_with_pipeline(pid))


@pytest.mark.asyncio
async def test_ensure_pipeline_exists_before_create_succeeds(
    fk_db_session: AsyncSession,
):
    """The supported ordering — Pipeline row first, then the job —
    flushes without an FK violation.  This is the order every mint
    site (year_configuration, /sync/recalculate-*, _chain.chain_job,
    _stamp_job_type_and_meta) MUST honor.
    """
    from uuid import uuid4

    pid = uuid4()
    repo = DataIngestionRepository(fk_db_session)

    # Correct order: ensure pipelines row, THEN insert the job.
    await repo.ensure_pipeline_exists(pid, kind="unit_sync", year=2026)
    created = await repo.create_ingestion_job(_job_with_pipeline(pid))

    assert created.id is not None
    assert created.pipeline_id == pid


@pytest.mark.asyncio
async def test_wrong_order_create_then_ensure_raises(
    fk_db_session: AsyncSession,
):
    """The historical wrong shape (data_sync.py 1559-1569 pre-fix):
    ``create_ingestion_job`` first, ``ensure_pipeline_exists`` second.
    ``create_ingestion_job`` flushes, the FK rejects, and
    ``ensure_pipeline_exists`` is never even reached.
    """
    from uuid import uuid4

    pid = uuid4()
    repo = DataIngestionRepository(fk_db_session)

    with pytest.raises(IntegrityError):
        await repo.create_ingestion_job(_job_with_pipeline(pid))
        # Unreachable — the flush above already raised.
        await repo.ensure_pipeline_exists(pid, kind="unit_sync", year=2026)


# ---------------------------------------------------------------------------
# Bug shape (3) — assigning ``row.pipeline_id`` BEFORE ``ensure_pipeline_exists``
# lets autoflush write the UPDATE while ``pipelines`` is empty.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dirty_pipeline_id_then_ensure_raises_via_autoflush(
    fk_db_session: AsyncSession,
):
    """Negative control for the ``_stamp_job_type_and_meta`` / chain_job
    bug.  A pre-existing job has ``pipeline_id = None``.  The bug
    assigns ``row.pipeline_id = pid`` first, then calls
    ``ensure_pipeline_exists`` — whose SELECT triggers autoflush,
    which writes UPDATE … pipeline_id=pid while ``pipelines`` is
    empty.  FK fires.
    """
    from uuid import uuid4

    pid = uuid4()
    repo = DataIngestionRepository(fk_db_session)

    # Step 1: create a job with NO pipeline_id (allowed; FK is nullable).
    job = _job_with_pipeline(None)
    created = await repo.create_ingestion_job(job)
    assert created.id is not None

    # Step 2: the BUGGY ordering — mark the row dirty FIRST.
    created.pipeline_id = pid
    fk_db_session.add(created)

    # Step 3: ``ensure_pipeline_exists`` SELECT triggers autoflush →
    # UPDATE fires before the Pipeline row INSERT → FK rejects.
    with pytest.raises(IntegrityError):
        await repo.ensure_pipeline_exists(pid, kind="csv_ingest", year=2026)


@pytest.mark.asyncio
async def test_ensure_then_dirty_pipeline_id_succeeds(
    fk_db_session: AsyncSession,
):
    """The supported ordering for the stamp/chain pattern: create the
    Pipeline row FIRST, then assign ``row.pipeline_id``.  The caller's
    eventual commit (or next autoflush) writes the UPDATE with the
    parent row already present → FK ok.
    """
    from uuid import uuid4

    pid = uuid4()
    repo = DataIngestionRepository(fk_db_session)

    job = _job_with_pipeline(None)
    created = await repo.create_ingestion_job(job)
    assert created.id is not None

    # Correct order: pipelines row FIRST.
    await repo.ensure_pipeline_exists(pid, kind="csv_ingest", year=2026)
    created.pipeline_id = pid
    fk_db_session.add(created)
    await fk_db_session.flush()

    assert created.pipeline_id == pid
