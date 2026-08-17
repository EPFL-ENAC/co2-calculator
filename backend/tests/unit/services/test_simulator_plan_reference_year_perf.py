"""Measurement + regression tests for plan 2050 section C3 (`set_reference_year` N+1).

Confirms, by measurement, the four static findings listed in
``docs/src/implementation-plans/2050-backend-compute-performance.md``
section C3, and pins the fix: ``_recalculate_report_emissions`` now shares
a ``FactorResolver``/factor-query cache and does one set-based delete +
bulk insert instead of a per-entry factor lookup + SELECT-then-DELETE.

Finding #2 (duplicate ``list_by_module`` call) and finding #3's own N+1
(``_persist_prefill_entries`` never got the ``override_cache`` batching
applied to ``_recalculate_report_emissions``) are fixed here too — a
production trace of a ~1000-entry plan hit exactly this: the request's
first ~70s produced zero DB spans because the *prefill* phase, not the
recalc phase, was issuing the per-entry ``session.get`` + sum-query
fallback. Finding #4 (per-year fan-out in ``_sync_year_reports``) is
structural and remains open — tracked as measurement-only here.

Mirrors ``tests/unit/services/test_simulator_plan_service.py``'s in-memory
sqlite fixture, extended to expose the engine so a
``before_cursor_execute`` listener can count SQL statements per call.
"""

import re
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.modules.emissions.taxonomy import EmissionType
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.carbon_report import CarbonReportCreate
from app.schemas.data_entry import DataEntryResponse
from app.schemas.simulator_plan import SimulatorPlanUpdate
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.simulator_plan_service import SimulatorPlanService

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

FACTOR_RE = re.compile(r"\bfactors\b", re.IGNORECASE)
EMISSION_RE = re.compile(r"\bdata_entry_emissions\b", re.IGNORECASE)
EMISSION_SELECT_RE = re.compile(
    r"^SELECT.*\bdata_entry_emissions\b", re.IGNORECASE | re.DOTALL
)
EMISSION_DELETE_RE = re.compile(
    r"^DELETE.*\bdata_entry_emissions\b", re.IGNORECASE | re.DOTALL
)
EMISSION_INSERT_RE = re.compile(
    r"^INSERT.*\bdata_entry_emissions\b", re.IGNORECASE | re.DOTALL
)


async def _set_ref(service, plan_id, year, reference_year, *, is_grant=False):
    """``set_reference_year`` plus the prefill its job now runs (Track F4).

    The route defers prefill to ``simulator_plan_prefill``; these tests
    exercise the combined effect, so they run both halves and re-read the
    year afterwards (the first read is built before prefill happens).
    """
    out = await service.set_reference_year(
        plan_id, year, reference_year, is_grant=is_grant
    )
    if out is None:
        return None
    _, needs_prefill = out
    await service.prefill_reports(needs_prefill)
    years = await service.list_plan_years(plan_id)
    return next(
        (y for y in years or [] if y.year == year and y.is_grant == is_grant), None
    )


async def _update_plan(service, plan_id, update):
    """``update_plan`` plus the prefill its job now runs (Track F4)."""
    out = await service.update_plan(plan_id, update)
    if out is None:
        return None
    result, needs_prefill = out
    await service.prefill_reports(needs_prefill)
    return result


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(DATABASE_URL, echo=False, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def async_session(engine):
    async_session = sessionmaker(
        engine, class_=SQLModelAsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def user(async_session):
    db_user = User(
        institutional_id="100001",
        email="ada@example.com",
        display_name="Ada Lovelace",
    )
    async_session.add(db_user)
    await async_session.flush()
    return db_user


@dataclass
class StatementLog:
    """Statements issued during a measured block, with wall time."""

    statements: list[str] = field(default_factory=list)
    wall_time: float = 0.0

    @property
    def total(self) -> int:
        return len(self.statements)

    @property
    def factor_lookups(self) -> int:
        return sum(1 for s in self.statements if FACTOR_RE.search(s))

    @property
    def emission_writes(self) -> int:
        return sum(1 for s in self.statements if EMISSION_RE.search(s))

    @property
    def emission_selects(self) -> int:
        """SELECTs against ``data_entry_emissions``.

        Before the fix, this counted the per-entry ``delete_by_data_entry_id``
        pre-delete SELECT (ORM ``session.delete()`` needs the objects in
        hand) — one per entry. The fix replaced that with a set-based
        DELETE, but added its own O(1) SELECT: ``prefetch_percentage_
        override_cache``'s batched GROUP BY sum over prefill sources.
        Alongside the pre-existing O(1) stats-rollup SELECT
        (``recompute_stats_many``), this now settles at <=2 per isolated
        ``_recalculate_report_emissions`` call — constant, not per-entry,
        instead of the old N+1. ``_prefill_reference_modules`` settles at
        its own higher-but-still-constant value instead (13 in this file's
        fixture): one stats-rollup SELECT per reference-scoped *module
        type* touched, not per entry — see
        ``test_prefill_reference_modules_isolated_statement_count``.
        """
        return sum(1 for s in self.statements if EMISSION_SELECT_RE.match(s.strip()))

    @property
    def emission_deletes(self) -> int:
        return sum(1 for s in self.statements if EMISSION_DELETE_RE.match(s.strip()))

    @property
    def emission_inserts(self) -> int:
        return sum(1 for s in self.statements if EMISSION_INSERT_RE.match(s.strip()))

    @property
    def non_insert_total(self) -> int:
        """Statement count excluding ``data_entry_emissions`` INSERTs.

        SQLite's ``bulk_copy`` fallback (``session.add_all`` + flush — see
        ``DataEntryEmissionRepository.bulk_copy``) issues one INSERT per
        row; production Postgres uses a single ``COPY FROM STDIN``. This
        isolates round-trip count from that test-harness-only artifact.
        """
        return self.total - self.emission_inserts

    def breakdown(self) -> str:
        return (
            f"total={self.total} factor_lookups={self.factor_lookups} "
            f"emission_selects={self.emission_selects} "
            f"emission_deletes={self.emission_deletes} "
            f"emission_inserts={self.emission_inserts} "
            f"wall_time={self.wall_time * 1000:.2f}ms"
        )


@contextmanager
def count_statements(engine):
    """Count SQL statements + wall time issued by the wrapped block.

    Registers on ``engine.sync_engine`` — DBAPI-level events fire on the
    sync engine that backs an async engine, regardless of the aiosqlite
    driver wrapping it.
    """
    log = StatementLog()

    def listener(conn, cursor, statement, parameters, context, executemany):
        log.statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", listener)
    start = time.perf_counter()
    try:
        yield log
    finally:
        log.wall_time = time.perf_counter() - start
        event.remove(engine.sync_engine, "before_cursor_execute", listener)


async def _reference_report_with_entries(
    service: SimulatorPlanService,
    async_session,
    count: int,
    *,
    unit_id: int,
    year: int = 2024,
):
    """A Calculator report for ``unit_id`` / ``year`` with ``count``
    process-emissions entries — the reference year copied by
    ``_prefill_reference_modules`` and then recomputed by
    ``_recalculate_report_emissions``.

    ``unit_id`` must be distinct per measurement in a shared in-memory DB:
    ``get_calculator_report(unit_id, year)`` is looked up by that pair, so
    reusing one unit/year across a small-N and a large-N run in the same
    session makes both resolve to whichever report was created first.
    """
    report = await service.report_service.create(
        CarbonReportCreate(year=year, unit_id=unit_id)
    )
    modules = await service.report_service.module_service.list_modules(report.id)
    module = next(
        m for m in modules if m.module_type_id == int(ModuleTypeEnum.process_emissions)
    )
    for i in range(count):
        async_session.add(
            DataEntry(
                data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
                carbon_report_module_id=module.id,
                data={"category": "co2", "quantity": float(i + 1)},
            )
        )
    await async_session.flush()
    return report, module


async def _plan_with_year(
    service: SimulatorPlanService, user, plan_name: str, year: int, *, unit_id: int
):
    plan = await service.create_plan(unit_id=unit_id, user=user, name=plan_name)
    await _update_plan(
        service, plan.id, SimulatorPlanUpdate(start_year=year, end_year=year)
    )
    return plan


# ── Finding #1: _recalculate_report_emissions was an N+1 per entry ────────────


async def _measure_set_reference_year(
    engine, async_session, user, *, entry_count: int, plan_name: str, unit_id: int
) -> StatementLog:
    service = SimulatorPlanService(async_session)
    await _reference_report_with_entries(
        service, async_session, entry_count, unit_id=unit_id
    )
    plan = await _plan_with_year(service, user, plan_name, year=2027, unit_id=unit_id)

    with count_statements(engine) as log:
        result = await _set_ref(service, plan.id, 2027, 2024)
    assert result is not None
    return log


@pytest.mark.asyncio
async def test_set_reference_year_statement_count_vs_entry_count(
    engine, async_session, user
):
    """End-to-end reproduction of the profiled PATCH request.

    Regression test for finding #1: before the fix,
    ``_recalculate_report_emissions`` built a fresh ``FactorResolver`` per
    entry (no shared cache) and did a per-entry DELETE+INSERT inside
    ``upsert_by_data_entry``, so statement count scaled ~linearly with
    entry count. After the fix, statement count grows with the number of
    distinct module types touched, not with entry count.

    Each measurement uses its own ``unit_id``: ``get_calculator_report``
    resolves by (unit_id, year), so sharing a unit across the small-N and
    large-N runs in this one in-memory DB would make both resolve to
    whichever report was created first, silently flattening the ratio.
    """
    small = await _measure_set_reference_year(
        engine, async_session, user, entry_count=10, plan_name="small", unit_id=1
    )
    large = await _measure_set_reference_year(
        engine, async_session, user, entry_count=50, plan_name="large", unit_id=2
    )

    print(f"\n[N=10]  {small.breakdown()}")
    print(f"[N=50]  {large.breakdown()}")
    print(
        f"ratio statements(N=50)/statements(N=10) = "
        f"{large.total / small.total:.2f}  (5.0 == perfectly linear in N)"
    )

    # A batched implementation costs O(1) round trips regardless of entry
    # count; only per-entry compute should grow. Ratio well under the ~5x
    # a 5x entry-count increase would give under O(N) round trips.
    assert large.total < small.total * 2, (
        f"statement count scales with entry count "
        f"({small.total} -> {large.total} for 10 -> 50 entries): "
        "finding #1 regressed (no factor_resolver/cache reuse in "
        "_recalculate_report_emissions)"
    )


@pytest.mark.asyncio
async def test_recalculate_report_emissions_isolated_statement_count(
    engine, async_session, user
):
    """Same measurement, isolated to ``_recalculate_report_emissions`` alone
    (reference year already set, prefill already done) — attributes the
    fixed cost to that method specifically rather than the prefill step.
    """
    service = SimulatorPlanService(async_session)

    async def isolated_recalc(entry_count: int, unit_id: int) -> StatementLog:
        await _reference_report_with_entries(
            service, async_session, entry_count, unit_id=unit_id
        )
        plan = await _plan_with_year(
            service, user, f"iso-{entry_count}", year=2027, unit_id=unit_id
        )
        report = await _set_ref(service, plan.id, 2027, 2024)
        assert report is not None
        reports = await service.repo.list_reports_for_project(plan.id)
        db_report = next(r for r in reports if r.id == report.id)
        with count_statements(engine) as log:
            await service._recalculate_report_emissions(db_report)  # noqa: SLF001
        return log

    small = await isolated_recalc(10, unit_id=11)
    large = await isolated_recalc(50, unit_id=12)

    print("\n[isolated _recalculate_report_emissions]")
    print(f"N=10  {small.breakdown()}")
    print(f"N=50  {large.breakdown()}")
    print(f"ratio={large.total / small.total:.2f}")

    assert large.total < small.total * 2, (
        f"_recalculate_report_emissions alone scales with entry count "
        f"({small.total} -> {large.total}): finding #1 regressed"
    )


async def _seed_process_emissions_factor(async_session, *, year: int = 2024) -> None:
    """A Factor row that lets ``category: "co2"`` entries actually compute
    and persist an emission — without it, ``FactorResolver.resolve`` finds
    nothing, ``prepare_create`` returns ``[]``, and the delete half of the
    replace never has anything to remove. Mirrors the fixture the rest of
    the suite runs factor-less; seeded only for this test.
    """
    async_session.add(
        Factor(
            emission_type_id=int(EmissionType.process_emissions__co2),
            data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
            classification={"category": "co2"},
            values={"ef_kg_co2eq_per_unit": 1.0},
            year=year,
        )
    )
    await async_session.flush()


@pytest.mark.asyncio
async def test_recalculate_report_emissions_large_n_delete_breakdown(
    engine, async_session, user
):
    """Larger-N confirmation: does the fix hold well past the small-N
    tests above, and is the per-entry SELECT-then-DELETE gone (matching
    "it's always the delete that pauses" from production profiling)?

    A matching Factor is seeded (see ``_seed_process_emissions_factor``) so
    entries actually compute and persist emissions on the first pass; the
    *second* ``_recalculate_report_emissions`` call is the one measured, so
    there are real existing emission rows to replace — the production
    shape (a reference year that already has computed emissions, changed
    again). 8000 was the original production-scale number the bug was
    measured at (see the historical 39.4x ratio cited below); this test
    uses 2000 — a 10x jump from the N=200 baseline is still decisive for
    an O(1)-vs-O(N) statement-count check, and keeps this file's runtime
    reasonable since it lives in ``tests/unit`` (default suite). Kept
    in-memory/sqlite here since this is a statement-count profile, not a
    wall-clock benchmark — sqlite ORM overhead differs from pooled
    Postgres, so only the ratio and the per-entry statement shape
    transfer, not the absolute wall time.
    """
    service = SimulatorPlanService(async_session)
    await _seed_process_emissions_factor(async_session)

    async def isolated_recalc(entry_count: int, unit_id: int) -> StatementLog:
        await _reference_report_with_entries(
            service, async_session, entry_count, unit_id=unit_id
        )
        plan = await _plan_with_year(
            service, user, f"bigN-{entry_count}", year=2027, unit_id=unit_id
        )
        report = await _set_ref(service, plan.id, 2027, 2024)
        assert report is not None
        reports = await service.repo.list_reports_for_project(plan.id)
        db_report = next(r for r in reports if r.id == report.id)
        # First pass: computes + persists real emissions (not measured).
        await service._recalculate_report_emissions(db_report)  # noqa: SLF001
        # Second pass: the one that matters — every entry now has an
        # existing emission row for the delete half of the replace to find.
        with count_statements(engine) as log:
            await service._recalculate_report_emissions(db_report)  # noqa: SLF001
        return log

    small = await isolated_recalc(200, unit_id=21)
    large = await isolated_recalc(2000, unit_id=22)

    print("\n[large-N delete breakdown, second pass over already-computed entries]")
    print(f"N=200   {small.breakdown()}")
    print(f"N=2000  {large.breakdown()}")
    print(
        f"ratio non_insert_total(2000)/non_insert_total(200) = "
        f"{large.non_insert_total / small.non_insert_total:.2f}  "
        "(1.0 == O(1) round trips)"
    )

    # The regression test: before the fix, N=200->8000 (a 40x entry
    # increase, production scale) measured a ~39.4x statement ratio — near-
    # perfectly linear. This test uses a smaller 10x jump (200->2000) for
    # CI runtime; a batched, set-based replace costs a small constant
    # number of round trips regardless of entry count either way.
    # Excludes INSERTs: SQLite's bulk_copy fallback writes one row per
    # INSERT (see ``non_insert_total``'s docstring), production Postgres
    # doesn't — that part of the ratio isn't this fix's concern.
    assert large.non_insert_total < small.non_insert_total * 2, (
        f"non-insert statement count scales with entry count on a second "
        f"(delete-heavy) pass ({small.non_insert_total} -> "
        f"{large.non_insert_total} for 200 -> 2000 entries): finding #1 "
        "regressed at production scale — the per-entry SELECT-then-DELETE "
        "or percentage-override lookup is back"
    )
    # The fix specifically targets two per-entry query shapes on
    # data_entry_emissions: the old SELECT-then-DELETE (delete_by_data_
    # entry_id), and the percentage-override sum (_sum_entry_emissions,
    # via _get_percentage_override_kg's source_data_entry_id fast path —
    # every plan-year entry is a prefill copy that carries it). Both are
    # now O(1) per recalc call: one set-based DELETE, one batched GROUP BY
    # SELECT (prefetch_percentage_override_cache).
    # <=2, not <=1: one is prefetch_percentage_override_cache's batched
    # GROUP BY sum, the other is the pre-existing O(1) stats-rollup SELECT
    # (recompute_stats_many) — both constant regardless of entry count.
    assert large.emission_selects <= 2, (
        f"expected at most 2 O(1) SELECTs against data_entry_emissions "
        f"(override-sum GROUP BY + stats rollup), got {large.emission_selects}"
    )
    assert large.emission_deletes <= 1, (
        f"expected at most 1 set-based DELETE (chunked by "
        f"bulk_replace_for_entries), got {large.emission_deletes}"
    )


@pytest.mark.asyncio
async def test_percentage_override_cache_matches_uncached_path(async_session, user):
    """Equivalence check for the C3 percentage-override batching.

    ``prefetch_percentage_override_cache`` must compute the same per-entry
    override kg as the original per-entry DB path (``session.get`` +
    ``_sum_entry_emissions``) — fewer statements must not mean a different
    number. The reference year's own emissions are computed first so the
    sums being compared are real, non-zero values, not both trivially 0.
    """
    service = SimulatorPlanService(async_session)
    await _seed_process_emissions_factor(async_session)
    ref_report, _ref_module = await _reference_report_with_entries(
        service, async_session, count=5, unit_id=41
    )
    await service._recalculate_report_emissions(ref_report)  # noqa: SLF001

    plan = await _plan_with_year(service, user, "equiv", year=2027, unit_id=41)
    result = await _set_ref(service, plan.id, 2027, 2024)
    assert result is not None
    reports = await service.repo.list_reports_for_project(plan.id)
    db_report = next(r for r in reports if r.id == result.id)
    assert db_report.id is not None

    entries = await DataEntryRepository(async_session).list_by_carbon_report(
        db_report.id
    )
    emission_svc = DataEntryEmissionService(async_session)
    cache = await emission_svc.prefetch_percentage_override_cache(
        entries, unit_id=db_report.unit_id
    )
    assert cache, "expected prefill entries to carry source_data_entry_id"

    nonzero_seen = False
    for entry in entries:
        response = DataEntryResponse.model_validate(entry)
        cached_kg = await emission_svc._get_percentage_override_kg(  # noqa: SLF001
            data_entry=response,
            emission_type=EmissionType.process_emissions__co2,
            report=db_report,
            override_cache=cache,
        )
        uncached_kg = await emission_svc._get_percentage_override_kg(  # noqa: SLF001
            data_entry=response,
            emission_type=EmissionType.process_emissions__co2,
            report=db_report,
            override_cache=None,
        )
        assert cached_kg == pytest.approx(uncached_kg), (
            f"entry {entry.id}: cached={cached_kg} != uncached={uncached_kg}"
        )
        nonzero_seen = nonzero_seen or bool(cached_kg)
    assert nonzero_seen, "expected at least one non-zero override kg to compare"


@pytest.mark.asyncio
async def test_recalculate_report_emissions_empty_still_refreshes_report_stats(
    async_session, user, monkeypatch: pytest.MonkeyPatch
):
    """Regression: the empty-entries early return must not skip the
    report-level stats refresh.

    The old per-entry loop called ``recompute_report_stats`` unconditionally
    at the end — only the module-level ``recompute_stats_many`` was gated on
    there being entries (``if module_ids:``). The batched rewrite's
    early-return-when-empty optimization (added for this same fix) initially
    skipped both, which would leave a report that just lost its last entry
    with stale ``stats``/``completion_progress``.
    """
    service = SimulatorPlanService(async_session)
    plan = await _plan_with_year(service, user, "empty-report", year=2027, unit_id=51)
    reports = await service.repo.list_reports_for_project(plan.id)
    report = reports[0]

    calls: list[int] = []
    original = service.report_service.recompute_report_stats

    async def counting_recompute(report_id: int):
        calls.append(report_id)
        return await original(report_id)

    monkeypatch.setattr(
        service.report_service, "recompute_report_stats", counting_recompute
    )

    await service._recalculate_report_emissions(report)  # noqa: SLF001

    assert calls == [report.id], (
        f"expected recompute_report_stats(report.id) to run even with no "
        f"entries, got {calls}"
    )


# ── Track F4: the PATCHes defer prefill to a job ──────────────────────────────


@pytest.mark.asyncio
async def test_set_reference_year_defers_prefill_instead_of_running_it(
    async_session, user
):
    """Setting a baseline must persist the year and hand the copy to the job.

    Regression test for plan #2050 Track F4: prefill used to run inside the
    request (21.9s on dev for one year of a ~5k-entry module). The call now
    returns the report ids needing prefill and leaves the modules empty
    until the job runs.
    """
    service = SimulatorPlanService(async_session)
    await _seed_process_emissions_factor(async_session)
    ref_report, _ = await _reference_report_with_entries(
        service, async_session, count=3, unit_id=91
    )
    await service._recalculate_report_emissions(ref_report)  # noqa: SLF001
    plan = await _plan_with_year(service, user, "f4-defer", year=2027, unit_id=91)

    out = await service.set_reference_year(plan.id, 2027, 2024)
    assert out is not None
    year_read, needs_prefill = out
    assert needs_prefill == [year_read.id], (
        "set_reference_year must hand back the report needing prefill"
    )

    module = next(
        m
        for m in year_read.modules
        if m.module_type_id == int(ModuleTypeEnum.process_emissions)
    )
    repo = DataEntryRepository(async_session)
    assert await repo.list_by_module(module.id) == [], (
        "prefill ran inside the request — Track F4 regressed"
    )

    # The job's half, run on its own, produces the rows.
    assert await service.prefill_reports(needs_prefill) == 1
    assert len(await repo.list_by_module(module.id)) == 3


@pytest.mark.asyncio
async def test_prefill_reports_is_idempotent_on_retry(async_session, user):
    """A preempted job re-runs from the start; it must converge, not duplicate.

    #1559 / the 310-series require this of every handler — prefill empties
    each module before rebuilding, so running it twice is the same as once.
    """
    service = SimulatorPlanService(async_session)
    await _seed_process_emissions_factor(async_session)
    ref_report, _ = await _reference_report_with_entries(
        service, async_session, count=3, unit_id=92
    )
    await service._recalculate_report_emissions(ref_report)  # noqa: SLF001
    plan = await _plan_with_year(service, user, "f4-retry", year=2027, unit_id=92)

    out = await service.set_reference_year(plan.id, 2027, 2024)
    assert out is not None
    _, needs_prefill = out

    await service.prefill_reports(needs_prefill)
    await service.prefill_reports(needs_prefill)

    years = await service.list_plan_years(plan.id)
    assert years is not None
    module = next(
        m
        for m in years[0].modules
        if m.module_type_id == int(ModuleTypeEnum.process_emissions)
    )
    entries = await DataEntryRepository(async_session).list_by_module(module.id)
    assert len(entries) == 3, f"retry duplicated rows: {len(entries)} != 3"


# ── Track F2: both prefill callers compute in one batched pass ────────────────


@pytest.mark.asyncio
async def test_sync_year_reports_computes_emissions_in_one_batched_pass(
    async_session, user, monkeypatch: pytest.MonkeyPatch
):
    """New plan-year creation must recompute the whole report once, not per module.

    Regression test for plan #2050 Track F2. ``_sync_year_reports`` used to
    compute emissions inside prefill, once per module: a cold
    ``FactorResolver`` + factor-query cache and a single-module
    ``recompute_stats_many`` for every module of every year. It now mirrors
    ``set_reference_year`` — insert the rows, then one
    ``_recalculate_report_emissions`` for the report — which shares one
    resolver/cache across every module and ends in one batched stats pass.

    Before the fix ``_prepare_recalc_emissions`` was never reached from this
    caller at all, so this fails without it.
    """
    service = SimulatorPlanService(async_session)
    await _seed_process_emissions_factor(async_session)
    await _reference_report_with_entries(service, async_session, count=2, unit_id=72)

    calls = 0
    original = service._prepare_recalc_emissions  # noqa: SLF001

    async def counting_prepare(*args, **kwargs):
        nonlocal calls
        calls += 1
        return await original(*args, **kwargs)

    monkeypatch.setattr(service, "_prepare_recalc_emissions", counting_prepare)

    plan = await service.create_plan(unit_id=72, user=user, name="f2-batched")
    await _update_plan(
        service,
        plan.id,
        SimulatorPlanUpdate(
            start_year=2027, end_year=2027, default_reference_year=2024
        ),
    )

    assert calls == 1, (
        f"expected one batched compute for the new year report, got {calls} — "
        "_sync_year_reports is computing per module again (Track F2 regressed)"
    )


@pytest.mark.asyncio
async def test_sync_year_reports_emissions_are_correct(async_session, user):
    """Correctness, not just call-count: routing new plan years through the
    batched recalc must persist the same kg values the per-module compute
    produced. A prefilled year whose rows carry no emissions is the silent
    failure this guards — the numbers are published.
    """
    service = SimulatorPlanService(async_session)
    await _seed_process_emissions_factor(async_session)
    ref_report, _ = await _reference_report_with_entries(
        service, async_session, count=2, unit_id=74
    )
    await service._recalculate_report_emissions(ref_report)  # noqa: SLF001

    plan = await service.create_plan(unit_id=74, user=user, name="f2-correct")
    await _update_plan(
        service,
        plan.id,
        SimulatorPlanUpdate(
            start_year=2027, end_year=2027, default_reference_year=2024
        ),
    )

    years = await service.list_plan_years(plan.id)
    assert years is not None
    module = next(
        m
        for m in years[0].modules
        if m.module_type_id == int(ModuleTypeEnum.process_emissions)
    )
    entries = await DataEntryRepository(async_session).list_by_module(module.id)
    assert {e.data["quantity"] for e in entries} == {1.0, 2.0}

    emission_repo = DataEntryEmissionService(async_session).repo
    kg_by_quantity = {}
    for e in entries:
        rows = await emission_repo.get_by_data_entry_id(e.id)
        assert rows, f"entry {e.id} has no persisted emissions"
        kg_by_quantity[e.data["quantity"]] = sum(r.kg_co2eq for r in rows)
    # ef_kg_co2eq_per_unit=1.0, copied at 100% → kg_co2eq == quantity.
    assert kg_by_quantity == {1.0: 1.0, 2.0: 2.0}


@pytest.mark.asyncio
async def test_set_reference_year_produces_correct_emissions_without_prefill_compute(
    async_session, user
):
    """Correctness, not just call-count: skipping prefill's own compute
    (tier 1) must not change the final emitted kg values —
    ``_recalculate_report_emissions`` alone must produce the same answer a
    prefill-then-recalc double-compute would have.
    """
    service = SimulatorPlanService(async_session)
    await _seed_process_emissions_factor(async_session)
    ref_report, _ = await _reference_report_with_entries(
        service, async_session, count=2, unit_id=73
    )
    await service._recalculate_report_emissions(ref_report)  # noqa: SLF001

    plan = await service.create_plan(unit_id=73, user=user, name="tier1-correct")
    await _update_plan(
        service, plan.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )
    plan_result = await _set_ref(service, plan.id, 2027, 2024)
    assert plan_result is not None

    module = next(
        m
        for m in plan_result.modules
        if m.module_type_id == int(ModuleTypeEnum.process_emissions)
    )
    entries = await DataEntryRepository(async_session).list_by_module(module.id)
    assert {e.data["quantity"] for e in entries} == {1.0, 2.0}

    emission_repo = DataEntryEmissionService(async_session).repo
    kg_by_quantity = {}
    for e in entries:
        rows = await emission_repo.get_by_data_entry_id(e.id)
        assert rows, f"entry {e.id} has no persisted emissions"
        kg_by_quantity[e.data["quantity"]] = sum(r.kg_co2eq for r in rows)
    # ef_kg_co2eq_per_unit=1.0 (see _seed_process_emissions_factor), so
    # kg_co2eq == quantity for each copied entry (100% of reference) — a
    # real, non-zero, non-default value, not just "some row exists."
    assert kg_by_quantity == {1.0: 1.0, 2.0: 2.0}


@pytest.mark.asyncio
async def test_modules_left_empty_by_prefill_still_get_their_stats_refreshed(
    async_session, user, monkeypatch: pytest.MonkeyPatch
):
    """Every module prefill leaves empty must still be refreshed — in ONE call.

    An empty module never appears in the later
    ``_recalculate_report_emissions``'s entry-driven module set, so prefill
    is its only chance to reflect "now empty" stats. Each such module used
    to issue its own single-module ``recompute_stats_many``; they are now
    batched (plan #2050 Track F6), so this pins both halves — the modules
    are still covered, and they cost one call rather than one each.
    """
    service = SimulatorPlanService(async_session)
    # A reference report with no entries at all: every rebuilt module of the
    # plan year ends up empty.
    await service.report_service.create(CarbonReportCreate(year=2024, unit_id=81))

    plan = await service.create_plan(unit_id=81, user=user, name="empty-modules")
    await _update_plan(
        service, plan.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )
    reports = await service.repo.list_reports_for_project(plan.id)
    report = reports[0]
    report.reference_year = 2024
    async_session.add(report)
    await async_session.flush()

    modules = await service.report_service.module_service.list_modules(report.id)
    headcount = next(
        m for m in modules if m.module_type_id == int(ModuleTypeEnum.headcount)
    )
    # Purchase is cleared but never rebuilt — the other half of the merge.
    purchase = next(
        m for m in modules if m.module_type_id == int(ModuleTypeEnum.purchase)
    )

    calls: list[list[int]] = []
    original = service.report_service.module_service.recompute_stats_many

    async def counting_recompute(module_ids, **kwargs):
        calls.append(sorted(module_ids))
        return await original(module_ids, **kwargs)

    monkeypatch.setattr(
        service.report_service.module_service,
        "recompute_stats_many",
        counting_recompute,
    )

    await service._prefill_reference_modules(report)  # noqa: SLF001

    covered = {module_id for call in calls for module_id in call}
    assert headcount.id in covered, (
        f"the empty headcount module never got its stats refreshed: {calls}"
    )
    assert purchase.id in covered, (
        f"the cleared purchase module never got its stats refreshed: {calls}"
    )
    # Cleared modules and prefill-emptied modules are the same case, so they
    # share one call — which keeps the report rollup behind it to one run.
    assert len(calls) == 1, (
        f"expected a single batched recompute_stats_many, got {len(calls)}: {calls}"
    )


@pytest.mark.asyncio
async def test_prefill_reference_modules_never_calls_get_module(
    async_session, user, monkeypatch: pytest.MonkeyPatch
):
    """``_prefill_reference_modules`` must satisfy every rebuilt module type's
    plan/reference module from its own ``list_modules`` calls — never a
    per-module-type ``get_module`` (plan #2050 Track E tier 2).

    Uses a plan with a Calculator reference year that has entries in
    multiple prefilled module types (process_emissions + headcount), so a
    regression that reintroduces even one ``get_module`` call shows up.
    """
    service = SimulatorPlanService(async_session)
    ref_report, _ = await _reference_report_with_entries(
        service, async_session, count=2, unit_id=91
    )
    ref_modules = await service.report_service.module_service.list_modules(
        ref_report.id
    )
    headcount_ref_module = next(
        m for m in ref_modules if m.module_type_id == int(ModuleTypeEnum.headcount)
    )
    async_session.add(
        DataEntry(
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=headcount_ref_module.id,
            data={"sius_code": "PROF", "fte": 1.0},
        )
    )
    await async_session.flush()

    plan = await _plan_with_year(service, user, "tier2-no-get", year=2027, unit_id=91)
    reports = await service.repo.list_reports_for_project(plan.id)
    report = reports[0]
    report.reference_year = 2024
    async_session.add(report)
    await async_session.flush()

    calls = 0
    original = service.report_service.module_service.get_module

    async def counting_get_module(*args, **kwargs):
        nonlocal calls
        calls += 1
        return await original(*args, **kwargs)

    monkeypatch.setattr(
        service.report_service.module_service, "get_module", counting_get_module
    )

    await service._prefill_reference_modules(report)  # noqa: SLF001

    assert calls == 0, (
        f"expected zero get_module calls (list_modules should cover every "
        f"rebuilt module type on both sides), got {calls}"
    )


# ── Finding #2: prefill_module_from_reference queried the same rows twice ─────
# Fixed: the copy loop now reuses the emptiness-check's ``src_entries``.


@pytest.mark.asyncio
async def test_prefill_module_from_reference_calls_list_by_module_once(
    async_session, user, monkeypatch: pytest.MonkeyPatch
):
    """Finding #2, fixed: ``entry_repo.list_by_module(ref_module.id)`` ran
    once for the emptiness check and again for the copy loop. The copy loop
    now iterates the already-fetched ``src_entries`` instead of re-querying.
    Counts calls directly rather than sniffing SQL text — deterministic
    regardless of backend.
    """
    service = SimulatorPlanService(async_session)
    report, module = await _reference_report_with_entries(
        service, async_session, count=5, unit_id=1
    )
    plan = await service.create_plan(unit_id=1, user=user, name="dup-check")
    await _update_plan(
        service, plan.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )
    reports = await service.repo.list_reports_for_project(plan.id)
    plan_report = reports[0]
    plan_report.reference_year = 2024
    async_session.add(plan_report)
    await async_session.flush()

    calls: list[int] = []
    original: Callable = DataEntryRepository.list_by_module

    async def counting_list_by_module(self, carbon_report_module_id):
        calls.append(carbon_report_module_id)
        return await original(self, carbon_report_module_id)

    monkeypatch.setattr(DataEntryRepository, "list_by_module", counting_list_by_module)

    await service.prefill_module_from_reference(
        plan_report, int(ModuleTypeEnum.process_emissions)
    )

    ref_module_calls = calls.count(module.id)
    print(f"\nlist_by_module(ref_module.id) called {ref_module_calls} time(s)")
    assert ref_module_calls == 1, (
        f"list_by_module(ref_module.id) was called {ref_module_calls} times "
        "(expected 1): finding #2 regressed — the copy loop is re-querying "
        "instead of reusing src_entries"
    )


# ── Finding #4: _sync_year_reports fans out per year ───────────────────────────
# Not touched by this fix — structural, measured only.


@pytest.mark.asyncio
async def test_sync_year_reports_statement_count_vs_year_count(
    engine, async_session, user
):
    """Finding #4: setting an N-year range with a default reference year
    calls ``_prefill_reference_modules`` + ``recompute_report_stats`` once per
    year inside a single ``update_plan`` — multiplying findings #1-#3 by the
    number of years. Measured, not asserted against (this fan-out is
    structural, not obviously a bug on its own — the plan calls it "the
    worst case", not incorrect), but the growth is reported here as the
    profile's second-priority target.
    """
    service = SimulatorPlanService(async_session)
    await _reference_report_with_entries(service, async_session, count=10, unit_id=1)

    short_plan = await service.create_plan(unit_id=1, user=user, name="short-range")
    with count_statements(engine) as short_log:
        await _update_plan(
            service,
            short_plan.id,
            SimulatorPlanUpdate(
                start_year=2027, end_year=2028, default_reference_year=2024
            ),
        )

    long_plan = await service.create_plan(unit_id=1, user=user, name="long-range")
    with count_statements(engine) as long_log:
        await _update_plan(
            service,
            long_plan.id,
            SimulatorPlanUpdate(
                start_year=2027, end_year=2031, default_reference_year=2024
            ),
        )

    print(
        f"\n[2 years] statements={short_log.total} "
        f"wall={short_log.wall_time * 1000:.2f}ms"
    )
    print(
        f"[5 years] statements={long_log.total} wall={long_log.wall_time * 1000:.2f}ms"
    )
    print(
        f"ratio statements(5y)/statements(2y) = "
        f"{long_log.total / short_log.total:.2f}  (2.5 == perfectly linear in years)"
    )
    # Reported, not asserted: per-year fan-out is structural (one report per
    # year is the feature), the plan flags it as a cost multiplier for
    # findings #1-#3, not as its own bug.


# ── Finding #3: _prefill_reference_modules had its own N+1, fixed ─────────────
# Every prefill copy carries source_data_entry_id (finding #2's own subject),
# and _persist_prefill_entries never got the override_cache batching applied
# to _recalculate_report_emissions — so the *prefill* phase, not recalc,
# re-triggered the per-entry session.get + sum-query fallback for every row.
# This is what a production ~1000-entry plan-year PATCH actually spent its
# first ~70s of DB-silent time on: prefill runs before recalc, so its cost
# fell outside the C3 finding-#1 measurement (which isolates
# _recalculate_report_emissions alone, after prefill has already run).


@pytest.mark.asyncio
async def test_prefill_reference_modules_isolated_statement_count(
    engine, async_session, user
):
    """Isolates ``_prefill_reference_modules`` (prefill only, no recalc).

    Before the fix, ``_persist_prefill_entries`` computed each prefilled
    row's percentage-override kg via the uncached ``session.get`` + sum-query
    path (every row carries ``source_data_entry_id``), so statement count
    scaled with entry count independent of finding #1's fix. After the fix,
    it shares ``prefetch_percentage_override_cache`` the same way recalc does.

    A matching Factor is seeded and the reference report's own emissions are
    computed first (as in production, where the reference year's Calculator
    entries are already computed): without a resolvable factor,
    ``resolve_computations`` yields no computations and the percentage-
    override branch — the thing this test measures — is never reached at
    all, silently passing regardless of the fix.
    """
    service = SimulatorPlanService(async_session)
    await _seed_process_emissions_factor(async_session)

    async def isolated_prefill(entry_count: int, unit_id: int) -> StatementLog:
        ref_report, _ref_module = await _reference_report_with_entries(
            service, async_session, entry_count, unit_id=unit_id
        )
        await service._recalculate_report_emissions(ref_report)  # noqa: SLF001
        plan = await _plan_with_year(
            service, user, f"prefill-{entry_count}", year=2027, unit_id=unit_id
        )
        reports = await service.repo.list_reports_for_project(plan.id)
        report = reports[0]
        report.reference_year = 2024
        async_session.add(report)
        await async_session.flush()
        with count_statements(engine) as log:
            await service._prefill_reference_modules(report)  # noqa: SLF001
        return log

    small = await isolated_prefill(10, unit_id=61)
    large = await isolated_prefill(50, unit_id=62)

    print("\n[isolated _prefill_reference_modules]")
    print(f"N=10  {small.breakdown()}")
    print(f"N=50  {large.breakdown()}")
    print(f"ratio total={large.total / small.total:.2f}")
    print(
        f"ratio emission_selects={large.emission_selects / small.emission_selects:.2f}"
    )

    # ``total`` alone doesn't discriminate here: SQLite's bulk_copy fallback
    # scales emission_inserts 5x regardless of this fix (one INSERT per row,
    # unlike production Postgres's single COPY — see StatementLog.
    # non_insert_total's docstring), which dilutes a per-entry SELECT
    # regression out of the raw total. emission_selects isolates the actual
    # bug: before the fix, N=10->50 measured 23->63 SELECTs against
    # data_entry_emissions (one _sum_entry_emissions call per prefilled row);
    # the fix flattens that to a small constant tied to module count
    # (finding #4's sibling — this method fans out per module type), not
    # entry count.
    assert large.emission_selects < small.emission_selects * 2, (
        f"emission_selects scales with entry count "
        f"({small.emission_selects} -> {large.emission_selects} for 10 -> 50 "
        "entries): finding #3's override-cache fix regressed "
        "(_persist_prefill_entries lost its prefetch_percentage_override_cache "
        "call, or prepare_create stopped receiving it)"
    )


# ── Second data point: a non-process_emissions module type ────────────────────


@pytest.mark.asyncio
async def test_recalculate_report_emissions_scales_for_purchase_module_too(
    engine, async_session, user
):
    """The fix is not specific to process_emissions: statement count stays
    ~constant for another module/handler too (purchase,
    ``scientific_equipment`` entries).

    Purchase is manual-input, not prefilled from a reference year (see
    ``_prefill_reference_modules``'s docstring — it is wiped on a baseline
    change but never rebuilt), so entries are added directly to the
    plan-year report's own purchase module, and ``_recalculate_report_emissions``
    is called directly rather than through ``set_reference_year``.
    """
    service = SimulatorPlanService(async_session)

    async def isolated_recalc(entry_count: int, unit_id: int) -> StatementLog:
        plan = await _plan_with_year(
            service, user, f"purchase-{entry_count}", year=2027, unit_id=unit_id
        )
        reports = await service.repo.list_reports_for_project(plan.id)
        report = reports[0]
        modules = await service.report_service.module_service.list_modules(report.id)
        purchase_module = next(
            m for m in modules if m.module_type_id == int(ModuleTypeEnum.purchase)
        )
        for i in range(entry_count):
            async_session.add(
                DataEntry(
                    data_entry_type_id=DataEntryTypeEnum.scientific_equipment.value,
                    carbon_report_module_id=purchase_module.id,
                    unit_id=unit_id,
                    year=report.year,
                    data={"amount": float(i + 1)},
                )
            )
        await async_session.flush()
        with count_statements(engine) as log:
            await service._recalculate_report_emissions(report)  # noqa: SLF001
        return log

    small = await isolated_recalc(10, unit_id=31)
    large = await isolated_recalc(50, unit_id=32)

    print("\n[purchase / scientific_equipment entries]")
    print(f"N=10  {small.breakdown()}")
    print(f"N=50  {large.breakdown()}")
    print(f"ratio={large.total / small.total:.2f}")

    assert large.total < small.total * 2, (
        f"purchase-module recalculation scales with entry count "
        f"({small.total} -> {large.total}): finding #1 regressed for a "
        "non-process_emissions module type too"
    )
