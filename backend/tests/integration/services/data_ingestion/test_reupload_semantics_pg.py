"""Real-Postgres tests pinning data/factor reupload semantics
(Plan 310 test-coverage batch, Unit 8/11).

Three contracts, all pinned against ``headcount.member`` as the
representative module-per-year scope:

1. **Data CSV reupload REPLACES**: a second ``data.csv`` upload for the
   same ``(module, det, year)`` deletes the prior CSV-sourced entries
   and inserts the new ones.  The new pipeline gets a fresh
   ``pipeline_id``; ``data_entries.count()`` after reupload reflects
   only the second CSV's row count, not a sum.  See
   ``base_csv_provider._delete_existing_entries_for_module_per_year``
   for the implementation.

2. **Factor reupload dedup under concurrency**: with PR #1074's
   ``uq_emission_recalc_active`` partial unique index, two factor
   reuploads firing the recalc chain back-to-back collapse to ONE
   active ``emission_recalc`` job — even when the two ``chain_job``
   calls run concurrently via ``asyncio.gather`` on separate sessions.
   The second writer trips the partial-unique-index race and
   ``_insert_child_with_dedup`` returns ``None``.

3. **kg_co2eq override is REPLACED, not preserved**: a row uploaded
   with an inline ``kg_co2eq`` override (carried via the
   ``__kg_co2eq_override__`` carrier on ``DataEntry.data``) does NOT
   survive a reupload that omits the override — replace semantics
   apply, the new (override-less) row wins.  Operators relying on a
   one-time inline override must keep it in every reupload of the
   same ``(module, det, year)``.

These tests exercise the real ``ModulePerYearCSVProvider`` end-to-end
(file move → CSV parse → bulk insert → chain fan-out) so the contract
is empirical, not stipulative.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
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
from app.services.data_entry_emission_service import KG_CO2EQ_OVERRIDE_KEY
from app.services.data_ingestion.csv_providers.module_per_year import (
    ModulePerYearCSVProvider,
)
from app.tasks._chain import EMISSION_RECALC_DEDUP, chain_job

from .conftest import (
    assert_stats_match,
    dispatch_csv_and_wait,
    seeded_year_with_units,
)

# Index installers — ``pg_dsn`` builds tables via ``SQLModel.metadata``,
# which never runs the Alembic migrations that create the partial unique
# indexes the dedup machinery binds to.  These mirror the DDL inline so
# the dedup pre-check + IntegrityError race surfaces both branches in CI.
# Same shape as the duplicates in ``test_emission_recalc_dedup_pg.py``,
# ``test_full_dag_pipeline_pg.py``, and ``test_foundation_smoke.py``;
# extracting to conftest is a cross-Unit refactor we deliberately defer.


async def _install_emission_recalc_dedup_index(engine) -> None:
    """Create ``uq_emission_recalc_active`` (PR #1074 partial unique index)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_emission_recalc_active "
                "ON data_ingestion_jobs "
                "(module_type_id, data_entry_type_id, year) "
                "WHERE job_type = 'emission_recalc' "
                "AND state IN ("
                "'NOT_STARTED'::ingestion_state_enum, "
                "'QUEUED'::ingestion_state_enum, "
                "'RUNNING'::ingestion_state_enum"
                ") "
                "AND module_type_id IS NOT NULL "
                "AND data_entry_type_id IS NOT NULL "
                "AND year IS NOT NULL"
            )
        )


async def _install_aggregation_dedup_index(engine) -> None:
    """Create ``uq_aggregation_active`` so the ``csv_ingest →
    emission_recalc → aggregation`` chain's dedup INSERT can pre-check
    + race-trip safely under ``BULK_PATH_PURE_ASYNC``."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_aggregation_active "
                "ON data_ingestion_jobs (module_type_id, year) "
                "WHERE job_type = 'aggregation' "
                "AND state IN ("
                "'NOT_STARTED'::ingestion_state_enum, "
                "'QUEUED'::ingestion_state_enum, "
                "'RUNNING'::ingestion_state_enum)"
            )
        )


# --------------------------------------------------------------------------- #
# CSV builders — minimal headcount.member rows shaped so the real provider   #
# accepts them: ``unit_institutional_id`` ties to a seeded Unit, the columns #
# match ``HeadCountCreate``'s field set, and ``position_category`` is in     #
# ``POSITION_CATEGORY_VALUES``.                                              #
# --------------------------------------------------------------------------- #


def _csv_with_unit_column(
    unit_institutional_id: str,
    rows: list[tuple[str, str]],
    *,
    overrides: dict[str, float] | None = None,
) -> str:
    """Build a headcount.member CSV with the ``unit_institutional_id``
    column the provider's ``_resolve_carbon_report_modules`` keys on.

    Layout (one column-list, one branch on the optional ``kg_co2eq``
    override column):

        unit_institutional_id,name,position_title,position_category,
        user_institutional_id,fte,note[,kg_co2eq]

    Every row is the same unit + a different (name, uid) pair so the
    deletion guard's ``(module, det, year)`` scope hits exactly the
    rows the prior upload wrote.
    """
    header_cols = [
        "unit_institutional_id",
        "name",
        "position_title",
        "position_category",
        "user_institutional_id",
        "fte",
        "note",
    ]
    if overrides:
        header_cols.append("kg_co2eq")
    lines = [",".join(header_cols)]
    for name, user_uid in rows:
        cols = [
            unit_institutional_id,
            name,
            "Adjoint",
            "professor",
            user_uid,
            "0.50",
            "",
        ]
        if overrides:
            kg = overrides.get(name)
            cols.append(f"{kg:.2f}" if kg is not None else "")
        lines.append(",".join(cols))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# tmp_path / files-store wiring — the base provider's _validate_file_path    #
# rejects absolute paths and requires a ``tmp/`` prefix; LocalFilesStore is  #
# rooted at ``settings.FILES_STORAGE_PATH``.  Each test sets that to its     #
# pytest tmp_path so a CSV written to ``<tmp_path>/tmp/<sub>/data.csv`` is   #
# readable as the relative ``tmp/<sub>/data.csv``.  Mirrors the rig in       #
# ``test_plan_310b_factor_reupload_endpoint_pg.py``.                         #
# --------------------------------------------------------------------------- #


def _redirect_files_storage(monkeypatch, tmp_path: Path) -> None:
    """Redirect ``LocalFilesStore`` to ``tmp_path`` and disable encryption.

    Both the request-handler-side provider (if any) and the runner-side
    provider see the new path because we patch the cached settings
    instance — both code paths re-read ``settings.FILES_STORAGE_PATH``
    via ``make_files_store`` lazily.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "FILES_STORAGE_PATH", str(tmp_path))
    # Plain-text CSVs in tests — production uses Fernet, but exercising
    # the encryption round-trip is out of scope here.
    monkeypatch.setattr(settings, "FILES_ENCRYPTION_KEY", "")
    monkeypatch.setattr(settings, "FILES_ENCRYPTION_SALT", "")


def _write_csv(tmp_path: Path, sub: str, body: str) -> str:
    """Write ``body`` to ``<tmp_path>/tmp/<sub>/data.csv`` and return the
    relative path the base provider's ``_validate_file_path`` accepts.

    Each upload uses a unique ``sub`` because the provider's
    ``_setup_and_validate`` MOVES the file out of ``tmp/`` and into
    ``processing/<job_id>/``.  Re-using the same ``tmp/`` path between
    uploads would break the second upload at the move step.
    """
    csv_dir = tmp_path / "tmp" / sub
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / "data.csv"
    csv_path.write_text(body)
    return f"tmp/{sub}/data.csv"


async def _read_member_entries(session: AsyncSession, crm_id: int) -> list[DataEntry]:
    """Read every ``headcount.member`` ``DataEntry`` under ``crm_id``.
    Used after each upload to assert on the post-state."""
    result = await session.execute(
        select(DataEntry).where(
            col(DataEntry.carbon_report_module_id) == crm_id,
            col(DataEntry.data_entry_type_id) == int(DataEntryTypeEnum.member),
        )
    )
    return list(result.scalars().all())


async def _demote_prior_is_current(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    module_type_id: int,
    data_entry_type_id: int,
    year: int,
    target_type: TargetType = TargetType.DATA_ENTRIES,
    ingestion_method: IngestionMethod = IngestionMethod.csv,
) -> None:
    """Clear ``is_current=True`` on prior jobs in the scope.

    In production, ``DataIngestionRepository.claim_job`` demotes any
    pending ``is_current`` sibling before flipping the new row to
    RUNNING.  The bare ``dispatch_csv_and_wait`` helper bypasses
    ``claim_job`` (it just commits ``state=FINISHED`` directly), so a
    second dispatch in the same scope would crash on the
    ``ix_data_ingestion_jobs_is_current_unique`` partial unique index.
    Mirror the demote here so the test reflects the production
    invariant rather than papering over it.
    """
    async with session_factory() as session:
        await session.execute(
            text(
                "UPDATE data_ingestion_jobs SET is_current = FALSE "
                "WHERE is_current = TRUE "
                "AND module_type_id = :module_type_id "
                "AND data_entry_type_id = :data_entry_type_id "
                "AND year = :year "
                "AND target_type = :target_type "
                "AND ingestion_method = :ingestion_method "
                "AND job_type = 'csv_ingest'"
            ),
            {
                "module_type_id": module_type_id,
                "data_entry_type_id": data_entry_type_id,
                "year": year,
                "target_type": target_type.name,
                "ingestion_method": ingestion_method.name,
            },
        )
        await session.commit()


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_data_reupload_replaces_old_rows(pg_dsn_with_310b, monkeypatch, tmp_path):
    """Pin: a second ``data.csv`` upload for the same
    ``(module=headcount, det=member, year)`` REPLACES the prior CSV
    entries — old rows are deleted, new rows inserted, and the second
    pipeline_id is distinct from the first.

    Empirical contract derived from
    ``base_csv_provider._delete_existing_entries_for_module_per_year``,
    which runs before each MODULE_PER_YEAR import to wipe entries
    matching ``(carbon_report_module, data_entry_type, source=
    CSV_MODULE_PER_YEAR)`` from prior uploads.  Manual-source rows are
    untouched (see ``DataEntrySourceEnum.USER_MANUAL`` skipped from the
    deletion query).
    """
    _redirect_files_storage(monkeypatch, tmp_path)
    engine = create_async_engine(pg_dsn_with_310b, future=True)
    await _install_emission_recalc_dedup_index(engine)
    await _install_aggregation_dedup_index(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Seed a year + 1 unit + the seven module CRMs.  The CSV's
    # ``unit_institutional_id`` column resolves to this unit.
    async with Sf() as s:
        seeded = await seeded_year_with_units(s, year=2025, n_units=1)
    unit_institutional_id = seeded.units[0].institutional_id
    headcount_crm = seeded.modules_by_unit_and_type[
        (seeded.units[0].id, int(ModuleTypeEnum.headcount))
    ]
    headcount_crm_id = headcount_crm.id

    # ── Upload #1: rows R1, R2 ─────────────────────────────────────────
    csv1_body = _csv_with_unit_column(
        unit_institutional_id,
        rows=[("Alice One", "U-001"), ("Bob Two", "U-002")],
    )
    csv1_path = _write_csv(tmp_path, "up1", csv1_body)

    parent1, _children1 = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv1_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=2025,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    assert parent1.state == IngestionState.FINISHED
    assert parent1.result == IngestionResult.SUCCESS, (
        f"upload #1 did not succeed: {parent1.status_message!r}"
    )
    pipeline1 = parent1.pipeline_id
    assert pipeline1 is not None, "csv_ingest must stamp a pipeline_id"

    # Snapshot ids/uids after upload #1 so we can prove deletion.
    async with Sf() as s:
        rows1 = await _read_member_entries(s, headcount_crm_id)
    assert len(rows1) == 2, f"upload #1 should have inserted 2 rows; got {len(rows1)}"
    uids_after_1 = sorted(r.data["user_institutional_id"] for r in rows1)
    assert uids_after_1 == ["U-001", "U-002"], uids_after_1
    ids_after_1 = {r.id for r in rows1}

    # ── Upload #2: rows R3, R4 (different content) ─────────────────────
    # Mirror the production claim-job demote so the second parent's
    # is_current=True INSERT doesn't trip the partial unique index
    # (see ``_demote_prior_is_current`` for the rationale).
    await _demote_prior_is_current(
        Sf,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=2025,
    )
    csv2_body = _csv_with_unit_column(
        unit_institutional_id,
        rows=[("Carol Three", "U-003"), ("Dave Four", "U-004")],
    )
    csv2_path = _write_csv(tmp_path, "up2", csv2_body)

    parent2, _children2 = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv2_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=2025,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    assert parent2.state == IngestionState.FINISHED
    assert parent2.result == IngestionResult.SUCCESS, (
        f"upload #2 did not succeed: {parent2.status_message!r}"
    )
    pipeline2 = parent2.pipeline_id
    assert pipeline2 != pipeline1, (
        "second upload should produce a fresh pipeline_id; got the same UUID"
    )

    async with Sf() as s:
        rows2 = await _read_member_entries(s, headcount_crm_id)

    # Replace, NOT append: post-reupload count is 2 (not 4).
    assert len(rows2) == 2, (
        f"reupload should REPLACE old rows; expected 2 entries after upload #2, "
        f"got {len(rows2)}.  If this is 4 the deletion guard "
        f"(_delete_existing_entries_for_module_per_year) regressed to append-only."
    )
    uids_after_2 = sorted(r.data["user_institutional_id"] for r in rows2)
    assert uids_after_2 == ["U-003", "U-004"], (
        f"reupload should have wiped R1/R2 and inserted R3/R4; got {uids_after_2}"
    )
    # The original rows' ids are gone — proves DELETE, not UPDATE.
    new_ids = {r.id for r in rows2}
    assert new_ids.isdisjoint(ids_after_1), (
        f"reupload should DELETE old rows (new ids: {new_ids}); the old ids "
        f"({ids_after_1}) reappeared, suggesting upsert-by-id rather than "
        "wipe-and-insert."
    )
    # All new rows are CSV-sourced (the deletion guard only wipes this source).
    for r in rows2:
        assert r.source == int(DataEntrySourceEnum.CSV_MODULE_PER_YEAR), (
            f"new rows should carry source=CSV_MODULE_PER_YEAR; "
            f"got source={r.source} on entry {r.id}"
        )

    # The aggregation chain ran after upload #2 — ``carbon_report_modules.stats``
    # must be a dict (chain landed on the right CRM).  Empty-subset check
    # because the seed has no factors for the headcount.member det, so the
    # numeric values stay at zero — but a missing/None stats here would be
    # a real regression: it'd mean the reupload's aggregation chain wrote
    # to a different CRM (no double-counting from upload #1's pipeline
    # leaking into upload #2's stats).
    async with Sf() as s:
        await assert_stats_match(s, headcount_crm_id, {})

    await engine.dispose()


@pytest.mark.asyncio
async def test_factor_reupload_dedup_via_partial_unique_index(pg_dsn):
    """Pin: with PR #1074's ``uq_emission_recalc_active`` partial
    unique index in place, two ``chain_job(emission_recalc, dedup_config
    =EMISSION_RECALC_DEDUP)`` calls fired CONCURRENTLY for the same
    ``(module, det, year)`` collapse to ONE active row.

    Why ``asyncio.gather`` instead of sequential calls (already covered
    by ``test_emission_recalc_dedup_pg.test_back_to_back_factor_reuploads_
    collapse_to_one_recalc``): the sequential test exercises the
    pre-check branch where the second call sees the row from the first
    call's commit and returns early.  This test exercises the genuine
    concurrent-race branch — both pre-checks return empty, both attempt
    INSERT, the partial unique index trips on the second one, and
    ``_insert_child_with_dedup``'s ``IntegrityError`` catch surfaces
    the same dedup signal.

    Each chain runs on its own engine + session-factory so the two
    concurrent ``chain_job`` calls don't serialize on a shared
    asyncpg connection.
    """
    engine = create_async_engine(pg_dsn, future=True)
    await _install_emission_recalc_dedup_index(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Seed a parent factor_ingest job — the chains are children of this row.
    async with Sf() as s:
        parent = DataIngestionJob(
            entity_type=EntityType.MODULE_PER_YEAR,
            module_type_id=int(ModuleTypeEnum.headcount),
            data_entry_type_id=int(DataEntryTypeEnum.member),
            year=2025,
            target_type=TargetType.FACTORS,
            ingestion_method=IngestionMethod.csv,
            provider=UserProvider.DEFAULT,
            state=IngestionState.RUNNING,
            is_current=True,
            job_type="factor_ingest",
        )
        s.add(parent)
        await s.commit()
        await s.refresh(parent)
        parent_id = parent.id

    # ``chain_job`` fires ``run_job`` via ``fire_and_forget`` after the
    # INSERT.  We patch ``fire_and_forget`` to a no-op so the tasks
    # don't actually run against the real session factory — the dedup
    # contract is purely about the row-creation step.

    def _drop_fire_and_forget(coro, *, name=None):
        coro.close()
        return None

    async def _fire_one_chain() -> int | None:
        """Open a fresh session, call chain_job, return the child id (or
        None on dedup hit).  Each invocation gets its own session/
        connection so the two callers can race genuinely."""
        async with Sf() as session:
            row = await session.get(DataIngestionJob, parent_id)
            return await chain_job(
                row,
                job_type="emission_recalc",
                module_type_id=int(ModuleTypeEnum.headcount),
                data_entry_type_id=int(DataEntryTypeEnum.member),
                year=2025,
                session=session,
                dedup_config=EMISSION_RECALC_DEDUP,
            )

    with patch(
        "app.tasks._chain.fire_and_forget",
        side_effect=_drop_fire_and_forget,
    ):
        # ``asyncio.gather`` co-schedules the two coroutines; with two
        # async sessions backed by separate connections, the pre-check
        # SELECTs interleave with the INSERTs.  When both pre-checks
        # return empty, the second INSERT will trip
        # ``uq_emission_recalc_active`` and the catch arm of
        # ``_insert_child_with_dedup`` returns ``None``.
        results = await asyncio.gather(_fire_one_chain(), _fire_one_chain())

    # Exactly one chain produced an id; the other is None (dedup'd).
    successful = [r for r in results if r is not None]
    deduped = [r for r in results if r is None]
    assert len(successful) == 1, (
        f"exactly one concurrent chain should win; got "
        f"successful={successful}, deduped={deduped}"
    )
    assert len(deduped) == 1, (
        f"the losing chain should return None (dedup'd); got results={results}"
    )

    # Empirically: only one active emission_recalc row exists for the scope.
    async with Sf() as session:
        rows = (
            (
                await session.execute(
                    select(DataIngestionJob).where(
                        DataIngestionJob.job_type == "emission_recalc",
                        DataIngestionJob.module_type_id
                        == int(ModuleTypeEnum.headcount),
                        DataIngestionJob.data_entry_type_id
                        == int(DataEntryTypeEnum.member),
                        DataIngestionJob.year == 2025,
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1, (
        f"expected exactly 1 emission_recalc row after concurrent fan-out; "
        f"got {len(rows)} rows: {[(r.id, r.state) for r in rows]}.  If this "
        "is 2, the partial unique index uq_emission_recalc_active is missing "
        "or the IntegrityError catch in _insert_child_with_dedup regressed."
    )
    assert rows[0].id == successful[0], (
        f"the surviving row should be the winning chain's child id; "
        f"got row.id={rows[0].id}, winner={successful[0]}"
    )

    await engine.dispose()


@pytest.mark.asyncio
async def test_data_reupload_replaces_kg_co2eq_overrides(
    pg_dsn_with_310b, monkeypatch, tmp_path
):
    """Pin: a row uploaded with ``kg_co2eq=42.0`` (override carrier)
    is REPLACED — not preserved — when the same ``(module, det, year)``
    is re-uploaded with the same logical row but no override.  Replace
    semantics extend to the ``__kg_co2eq_override__`` carrier on
    ``DataEntry.data``: there's no row-level survival policy that
    re-attaches a prior override to a re-inserted entry.

    Operators relying on a one-time inline override must keep it in
    every reupload of the same scope.  The first pass at this contract
    might assume "override sticky" — empirically, the carrier is just
    a column inside ``DataEntry.data`` and the row gets DELETEd before
    the new one is INSERTed, so nothing carries over.
    """
    _redirect_files_storage(monkeypatch, tmp_path)
    engine = create_async_engine(pg_dsn_with_310b, future=True)
    await _install_emission_recalc_dedup_index(engine)
    await _install_aggregation_dedup_index(engine)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        seeded = await seeded_year_with_units(s, year=2025, n_units=1)
    unit_institutional_id = seeded.units[0].institutional_id
    headcount_crm = seeded.modules_by_unit_and_type[
        (seeded.units[0].id, int(ModuleTypeEnum.headcount))
    ]
    headcount_crm_id = headcount_crm.id

    # ── Upload #1: one row with kg_co2eq=42.0 override ─────────────────
    override_value = 42.0
    csv1_body = _csv_with_unit_column(
        unit_institutional_id,
        rows=[("Alice One", "U-001")],
        overrides={"Alice One": override_value},
    )
    csv1_path = _write_csv(tmp_path, "ovr1", csv1_body)

    parent1, _ = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv1_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=2025,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    assert parent1.result == IngestionResult.SUCCESS, (
        f"upload #1 (with override) did not succeed: {parent1.status_message!r}"
    )

    async with Sf() as s:
        rows1 = await _read_member_entries(s, headcount_crm_id)
    assert len(rows1) == 1, f"upload #1 should produce 1 row; got {len(rows1)}"
    # Sanity-check the carrier landed on the row's data dict (proves the
    # override was actually applied — without this, test 3 would silently
    # always pass because there'd be nothing to "replace").
    persisted_override = rows1[0].data.get(KG_CO2EQ_OVERRIDE_KEY)
    assert persisted_override == pytest.approx(override_value, rel=1e-6), (
        f"upload #1 should have persisted kg_co2eq override on the row's "
        f"{KG_CO2EQ_OVERRIDE_KEY} carrier; got {persisted_override!r} on "
        f"data={rows1[0].data!r}"
    )

    # ── Upload #2: same logical row, NO override column at all ─────────
    await _demote_prior_is_current(
        Sf,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=2025,
    )
    csv2_body = _csv_with_unit_column(
        unit_institutional_id,
        rows=[("Alice One", "U-001")],
        # No ``overrides`` arg → CSV header has no ``kg_co2eq`` column.
    )
    csv2_path = _write_csv(tmp_path, "ovr2", csv2_body)

    parent2, _ = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv2_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=2025,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    assert parent2.result == IngestionResult.SUCCESS, (
        f"upload #2 (no override) did not succeed: {parent2.status_message!r}"
    )

    async with Sf() as s:
        rows2 = await _read_member_entries(s, headcount_crm_id)

    # Still 1 row (replace, not append) but the override is GONE — the
    # second upload's row has no ``__kg_co2eq_override__`` carrier.
    assert len(rows2) == 1, (
        f"reupload should REPLACE — expected exactly 1 row, got {len(rows2)}"
    )
    assert rows2[0].id != rows1[0].id, (
        "reupload should DELETE the prior row and INSERT a fresh one — "
        f"got the same id {rows2[0].id} both times, suggesting upsert "
        "semantics rather than wipe-and-insert."
    )
    # The contract: override is REPLACED with absence, not preserved.
    assert KG_CO2EQ_OVERRIDE_KEY not in rows2[0].data, (
        f"reupload without an override column should DROP the prior "
        f"{KG_CO2EQ_OVERRIDE_KEY} carrier — replace semantics apply.  "
        f"Got data={rows2[0].data!r}.  If this assert flips in the "
        "future, document the new override-survival contract here."
    )

    await engine.dispose()
