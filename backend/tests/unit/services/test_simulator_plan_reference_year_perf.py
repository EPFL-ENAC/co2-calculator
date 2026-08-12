"""Measurement + regression tests for plan 2050 section C3 (`set_reference_year` N+1).

Confirms, by measurement, the four static findings listed in
``docs/src/implementation-plans/2050-backend-compute-performance.md``
section C3, and pins the fix: ``_recalculate_report_emissions`` now shares
a ``FactorResolver``/factor-query cache and does one set-based delete +
bulk insert instead of a per-entry factor lookup + SELECT-then-DELETE.

Findings #2 and #4 (duplicate ``list_by_module`` call, per-year fan-out in
``_sync_year_reports``) are unaffected by this fix and remain open —
tracked as measurement-only here.

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
        (``recompute_stats_many``), this now settles at <=2 per recalc
        call — constant, not per-entry — instead of the old N+1.
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
    await service.update_plan(
        plan.id, SimulatorPlanUpdate(start_year=year, end_year=year)
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
        result = await service.set_reference_year(plan.id, 2027, 2024)
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
        report = await service.set_reference_year(plan.id, 2027, 2024)
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
        report = await service.set_reference_year(plan.id, 2027, 2024)
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
    result = await service.set_reference_year(plan.id, 2027, 2024)
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


# ── Finding #2: prefill_module_from_reference queries the same rows twice ─────
# Not touched by this fix — still open, tracked as measurement only.


@pytest.mark.asyncio
async def test_prefill_module_from_reference_calls_list_by_module_twice(
    async_session, user, monkeypatch: pytest.MonkeyPatch
):
    """Finding #2 (open, not fixed here): ``entry_repo.list_by_module(
    ref_module.id)`` runs once for the emptiness check (line 484) and again
    for the copy loop (line 497). Counts calls directly rather than
    sniffing SQL text — deterministic regardless of backend. Asserts the
    *current* (unfixed) count so this test documents the open finding
    instead of silently going stale; flip to ``== 1`` when #2 is fixed.
    """
    service = SimulatorPlanService(async_session)
    report, module = await _reference_report_with_entries(
        service, async_session, count=5, unit_id=1
    )
    plan = await service.create_plan(unit_id=1, user=user, name="dup-check")
    await service.update_plan(
        plan.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
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
    assert ref_module_calls == 2, (
        f"list_by_module(ref_module.id) was called {ref_module_calls} times "
        "(expected 2, the known-open finding #2) — update this test if "
        "the duplicate call was fixed"
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
        await service.update_plan(
            short_plan.id,
            SimulatorPlanUpdate(
                start_year=2027, end_year=2028, default_reference_year=2024
            ),
        )

    long_plan = await service.create_plan(unit_id=1, user=user, name="long-range")
    with count_statements(engine) as long_log:
        await service.update_plan(
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
