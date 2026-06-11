"""Plan 310 test-coverage Unit 5/11 — headcount (member, student).

Pins the bulk-pipeline contract for headcount data uploads:

1. **CSV upload persists rows** — DataEntry rows land with
   ``source=DataEntrySourceEnum.CSV_MODULE_PER_YEAR``, exactly as the
   real ``ModulePerYearCSVProvider`` writes them.  No
   ``primary_factor_id`` on headcount entries (Strategy B handler —
   factor link is resolved from classification at compute time).

2. **No emissions until factors arrive** — the recalc workflow runs as
   part of the chain, but with no matching factor in the DB the
   Strategy B classification query in
   ``DataEntryEmissionService._fetch_factors`` returns ``[]``, so no
   ``data_entry_emissions`` rows are written.

3. **Factor presence triggers Strategy B recompute** — when factors are
   seeded ahead of (or before re-running) the chain,
   ``upsert_by_data_entry`` produces one emission row per
   ``EmissionComputation`` returned by the headcount handler's
   ``resolve_computations``.  ``kg_co2eq`` per row equals
   ``ef_kg_co2eq_per_unit × number_of_unit_per_fte × fte`` (the headcount
   formula: quantity_key=fte, multiplier_key=number_of_unit_per_fte,
   formula_key=ef_kg_co2eq_per_unit).

4. **FTE-weighted stats** — after the aggregation child runs,
   ``carbon_report_modules.stats`` reflects sums weighted by FTE across
   all entries.  ``stats.by_emission_type[<leaf>]`` equals the sum of
   per-entry kg_co2eq for that leaf.

5. **Reupload triggers recompute** — re-driving the chain with the same
   ``DataEntry`` rows mutated to different FTEs causes the aggregation
   handler to refresh ``stats`` to the new totals.

Strategy
--------
Driving a true CSV ingest end-to-end (LocalFilesStore + Fernet encryption
+ HTTP dispatch) is the territory of
``test_plan_310b_factor_reupload_endpoint_pg.py``.  For chain plumbing +
stats coverage in 11 worker units, this file uses
``dispatch_csv_and_wait`` (foundation helper) with a stub provider that
**writes the DataEntry rows itself** during ``ingest()`` — exactly what
the real provider would have done after parsing the CSV.  The chain
(``csv_ingest`` → ``emission_recalc`` → ``aggregation``) then runs
against those rows on the test PG.

Factor-change propagation for headcount/member and headcount/student is
already pinned by ``test_strategy_b_rematch_pg.py``; this file does not
duplicate those assertions.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
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

from .conftest import (
    assert_stats_match,
    csv_fixture_path,
    dispatch_csv_and_wait,
    seeded_year_with_units,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_writing_csv_provider(
    *,
    module_id: int,
    data_entry_type: DataEntryTypeEnum,
    rows: list[dict[str, Any]],
) -> type:
    """Build a stub provider class that writes ``rows`` as DataEntry rows.

    Mimics ``ModulePerYearCSVProvider``'s post-parse persistence step:
    each entry lands with ``source=CSV_MODULE_PER_YEAR`` and the supplied
    ``data`` payload.  No ``primary_factor_id`` — headcount is Strategy
    B (factor link resolved from classification at compute time).

    The provider receives the test's ``data_session`` via
    ``dispatch_csv_and_wait``'s plumbing and writes through it; the
    helper commits after the handler returns, so subsequent steps in the
    chain see the rows.

    Returns the class so callers can pass it as
    ``provider_class=...`` to ``dispatch_csv_and_wait``.
    """

    class WritingProvider:
        # ``dispatch_csv_and_wait`` derives ``meta.provider_name`` from
        # ``provider_class.__name__``, so the runner's
        # ``ProviderFactory.get_provider_class`` call (patched to return
        # this same class) lines up.
        def __init__(self, config, user=None, job_session=None, *, data_session=None):
            self.config = config
            self.user = user
            self.job_session = job_session
            self.data_session = data_session
            self.defer_finalize = False

        async def set_job_id(self, job_id):
            return None

        async def ingest(self, filters):
            for row_data in rows:
                entry = DataEntry(
                    data_entry_type_id=int(data_entry_type),
                    carbon_report_module_id=module_id,
                    data=dict(row_data),
                    source=DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value,
                )
                self.data_session.add(entry)
            await self.data_session.flush()
            return {
                "status_message": "ok",
                "data": {"result": IngestionResult.SUCCESS, "inserted": len(rows)},
            }

    return WritingProvider


# ``(headcount_category, headcount_class, emission_type, ef, multiplier)``
# tuples — single source of truth for both factor seeding and expected
# kg_co2eq computation.  Numbers chosen so each leaf's contribution is
# distinct and FTE-weighted totals are easy to verify by inspection.
_HEADCOUNT_LEAVES: list[tuple[str, str, EmissionType, float, float]] = [
    ("food", "vegetarian", EmissionType.food__vegetarian, 1.0, 100.0),
    ("waste", "incineration", EmissionType.waste__incineration, 0.5, 50.0),
    (
        "commuting",
        "public_transport",
        EmissionType.commuting__public_transport,
        0.2,
        200.0,
    ),
]


def _seeded_factors(data_entry_type: DataEntryTypeEnum, year: int) -> list[Factor]:
    """Build the 3 Strategy B headcount factors for ``data_entry_type``,
    covering food / waste / commuting (the three roots in
    ``MODULE_TYPE_TO_EMISSION_ROOTS[headcount]``)."""
    return [
        Factor(
            emission_type_id=emission.value,
            data_entry_type_id=data_entry_type.value,
            classification={"headcount_category": cat, "headcount_class": cls},
            values={
                "ef_kg_co2eq_per_unit": ef,
                "number_of_unit_per_fte": mult,
            },
            year=year,
        )
        for cat, cls, emission, ef, mult in _HEADCOUNT_LEAVES
    ]


def _expected_kg_per_leaf(fte: float) -> dict[int, float]:
    """``{emission_type_id: fte × multiplier × ef}`` for every leaf in
    ``_HEADCOUNT_LEAVES`` — matches the headcount handler's
    ``EmissionComputation`` (formula_key=ef, quantity_key=fte,
    multiplier_key=number_of_unit_per_fte)."""
    return {
        emission.value: fte * mult * ef
        for _, _, emission, ef, mult in _HEADCOUNT_LEAVES
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_headcount_member_csv_no_factors_persists_entries_without_emissions(
    pg_dsn,
):
    """**Member, no factors yet.**

    Drive ``csv_ingest`` for ``DataEntryTypeEnum.member`` against a fresh
    schema with no factors seeded.  After the chain finishes:

    - Every row in the stub's payload is persisted as a ``DataEntry``
      with ``source=CSV_MODULE_PER_YEAR.value`` and no
      ``primary_factor_id`` (Strategy B — never on the entry).
    - ``data_entry_emissions`` is empty for these entries — the
      classification query in ``_fetch_factors`` finds nothing.
    - ``carbon_report_modules.stats`` is still a dict (aggregation runs
      even on empty data) but ``by_emission_type`` is empty.

    Pins the "factor-deferred" half of the headcount Strategy B
    contract.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    year = 2025
    async with Sf() as s:
        seeded = await seeded_year_with_units(s, year=year, n_units=1)

    unit_id = seeded.units[0].id
    crm = seeded.modules_by_unit_and_type[(unit_id, int(ModuleTypeEnum.headcount))]
    assert crm.id is not None
    crm_id: int = crm.id

    member_rows = [
        {
            "name": f"Member {i}",
            "user_institutional_id": f"M-{i:03d}",
            "fte": fte,
            "position_category": "professor",
        }
        for i, fte in enumerate([1.0, 0.8, 0.5], start=1)
    ]

    csv_path = csv_fixture_path("headcount", "data")
    provider_class = _make_writing_csv_provider(
        module_id=crm_id,
        data_entry_type=DataEntryTypeEnum.member,
        rows=member_rows,
    )

    parent, _children = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=year,
        ingestion_method=IngestionMethod.csv,
        provider_class=provider_class,
    )

    assert parent.state == IngestionState.FINISHED
    assert parent.result == IngestionResult.SUCCESS

    async with Sf() as s:
        entries = (
            (
                await s.execute(
                    select(DataEntry).where(
                        col(DataEntry.carbon_report_module_id) == crm_id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(entries) == len(member_rows), (
        f"expected {len(member_rows)} DataEntry rows; got {len(entries)}"
    )
    for entry in entries:
        assert entry.source == DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value, (
            f"entry id={entry.id} source={entry.source}, expected "
            f"{DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value} "
            f"(CSV_MODULE_PER_YEAR)"
        )
        assert "primary_factor_id" not in entry.data, (
            "headcount is Strategy B: primary_factor_id must NOT live on "
            f"entry.data; got {entry.data!r}"
        )
        assert entry.data_entry_type_id == DataEntryTypeEnum.member.value

    async with Sf() as s:
        emissions = (
            (
                await s.execute(
                    select(DataEntryEmission).where(
                        col(DataEntryEmission.data_entry_id).in_(
                            [e.id for e in entries]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
    assert emissions == [], (
        "Strategy B without factors must not produce any emission rows; "
        f"got {len(emissions)}"
    )

    async with Sf() as s:
        await assert_stats_match(s, crm_id, {"by_emission_type": {}})

    await engine.dispose()


@pytest.mark.asyncio
async def test_headcount_member_csv_with_factors_produces_fte_weighted_stats(
    pg_dsn,
):
    """**Member, factors seeded — full chain emits + FTE-weighted stats.**

    Seed the three member factors (food / waste / commuting) ahead of the
    CSV chain.  After ``csv_ingest → emission_recalc → aggregation``:

    - Every persisted ``DataEntry`` produces exactly 3 emission rows
      (one per ``EmissionComputation`` returned by
      ``HeadcountMemberModuleHandler.resolve_computations``).
    - ``kg_co2eq`` per leaf row equals
      ``fte × number_of_unit_per_fte × ef_kg_co2eq_per_unit``.
    - ``stats.by_emission_type[<leaf>]`` equals the **sum across all
      entries** of that leaf's per-entry kg — i.e. FTE-weighted.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    year = 2025
    async with Sf() as s:
        seeded = await seeded_year_with_units(s, year=year, n_units=1)
        s.add_all(_seeded_factors(DataEntryTypeEnum.member, year))
        await s.commit()

    unit_id = seeded.units[0].id
    crm = seeded.modules_by_unit_and_type[(unit_id, int(ModuleTypeEnum.headcount))]
    assert crm.id is not None
    crm_id: int = crm.id

    ftes = [1.0, 0.8, 0.5]
    member_rows = [
        {
            "name": f"Member {i}",
            "user_institutional_id": f"M-{i:03d}",
            "fte": fte,
            "position_category": "professor",
        }
        for i, fte in enumerate(ftes, start=1)
    ]

    csv_path = csv_fixture_path("headcount", "data")
    provider_class = _make_writing_csv_provider(
        module_id=crm_id,
        data_entry_type=DataEntryTypeEnum.member,
        rows=member_rows,
    )

    parent, _children = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=year,
        ingestion_method=IngestionMethod.csv,
        provider_class=provider_class,
    )

    assert parent.state == IngestionState.FINISHED
    assert parent.result == IngestionResult.SUCCESS

    # Per-entry emissions: 3 leaves (food + waste + commuting) per
    # DataEntry, all with kg = fte × multiplier × ef.
    async with Sf() as s:
        entries = (
            (
                await s.execute(
                    select(DataEntry).where(
                        col(DataEntry.carbon_report_module_id) == crm_id
                    )
                )
            )
            .scalars()
            .all()
        )
        entry_id_to_fte: dict[int, float] = {
            e.id: float(e.data["fte"]) for e in entries
        }

        emissions = (
            (
                await s.execute(
                    select(DataEntryEmission).where(
                        col(DataEntryEmission.data_entry_id).in_(list(entry_id_to_fte))
                    )
                )
            )
            .scalars()
            .all()
        )

    leaf_ids = {emission.value for _, _, emission, _, _ in _HEADCOUNT_LEAVES}
    leaf_emissions = [e for e in emissions if e.emission_type_id in leaf_ids]
    assert len(leaf_emissions) == len(entry_id_to_fte) * len(leaf_ids), (
        f"expected {len(entry_id_to_fte) * len(leaf_ids)} leaf emissions "
        f"({len(leaf_ids)} per entry × {len(entry_id_to_fte)} entries); "
        f"got {len(leaf_emissions)}"
    )

    for em in leaf_emissions:
        fte = entry_id_to_fte[em.data_entry_id]
        expected = _expected_kg_per_leaf(fte)[em.emission_type_id]
        assert em.kg_co2eq == pytest.approx(expected, rel=1e-6), (
            f"emission entry={em.data_entry_id} leaf={em.emission_type_id}: "
            f"kg_co2eq={em.kg_co2eq}, expected fte({fte}) × multiplier × ef = "
            f"{expected}"
        )

    # FTE-weighted module stats: sum across all entries per leaf.
    expected_by_leaf: dict[int, float] = {leaf_id: 0.0 for leaf_id in leaf_ids}
    for fte in ftes:
        for leaf_id, kg in _expected_kg_per_leaf(fte).items():
            expected_by_leaf[leaf_id] += kg
    expected_total = sum(expected_by_leaf.values())

    async with Sf() as s:
        await assert_stats_match(
            s,
            crm_id,
            {
                "by_emission_type": {
                    str(leaf_id): pytest.approx(kg, rel=1e-6)
                    for leaf_id, kg in expected_by_leaf.items()
                },
                "total": pytest.approx(expected_total, rel=1e-6),
                "entry_count": len(ftes),
            },
        )

    await engine.dispose()


@pytest.mark.asyncio
async def test_headcount_student_csv_with_factors_produces_fte_weighted_stats(
    pg_dsn,
):
    """**Student, factors seeded — same shape as member.**

    ``HeadcountStudentModuleHandler`` mirrors the member handler on
    ``DataEntryTypeEnum.student`` (different ``data_entry_type_id`` →
    different factor classification keys).  Pin that the chain works
    identically: 3 emission leaves per entry, FTE-weighted stats summing
    across entries.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    year = 2025
    async with Sf() as s:
        seeded = await seeded_year_with_units(s, year=year, n_units=1)
        s.add_all(_seeded_factors(DataEntryTypeEnum.student, year))
        await s.commit()

    unit_id = seeded.units[0].id
    crm = seeded.modules_by_unit_and_type[(unit_id, int(ModuleTypeEnum.headcount))]
    assert crm.id is not None
    crm_id: int = crm.id

    ftes = [1.0, 0.5]
    student_rows = [{"fte": fte} for fte in ftes]

    csv_path = csv_fixture_path("headcount", "data")
    provider_class = _make_writing_csv_provider(
        module_id=crm_id,
        data_entry_type=DataEntryTypeEnum.student,
        rows=student_rows,
    )

    parent, _children = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.student),
        year=year,
        ingestion_method=IngestionMethod.csv,
        provider_class=provider_class,
    )

    assert parent.state == IngestionState.FINISHED
    assert parent.result == IngestionResult.SUCCESS

    async with Sf() as s:
        entries = (
            (
                await s.execute(
                    select(DataEntry).where(
                        col(DataEntry.carbon_report_module_id) == crm_id
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(entries) == len(ftes)
    for entry in entries:
        assert entry.data_entry_type_id == DataEntryTypeEnum.student.value
        assert entry.source == DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value

    expected_by_leaf: dict[int, float] = {
        emission.value: 0.0 for _, _, emission, _, _ in _HEADCOUNT_LEAVES
    }
    for fte in ftes:
        for leaf_id, kg in _expected_kg_per_leaf(fte).items():
            expected_by_leaf[leaf_id] += kg
    expected_total = sum(expected_by_leaf.values())

    async with Sf() as s:
        await assert_stats_match(
            s,
            crm_id,
            {
                "by_emission_type": {
                    str(leaf_id): pytest.approx(kg, rel=1e-6)
                    for leaf_id, kg in expected_by_leaf.items()
                },
                "total": pytest.approx(expected_total, rel=1e-6),
                "entry_count": len(ftes),
            },
        )

    await engine.dispose()


@pytest.mark.asyncio
async def test_headcount_member_reupload_with_new_ftes_refreshes_stats(
    pg_dsn,
):
    """**Reupload — stats refresh to the new FTE totals.**

    Re-driving the chain with ``DataEntry`` rows whose ``data['fte']``
    has been mutated must produce ``stats`` reflecting the *new* totals,
    not the previous run's.

    To avoid relying on the bulk-CSV "delete previous" path (the stub
    provider does not implement ``_delete_existing_entries_for_module_per_year``
    — the helper-driven test path doesn't see the real provider's
    pre-write delete), we mutate the ``fte`` field on the existing
    entries directly between dispatches and assert the recompute paints
    the new values.  The contract being pinned is "recompute fires on
    re-dispatch + new totals land in stats", not "old rows get garbage
    collected" — that belongs to a real-CSV-provider test.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    year = 2025
    async with Sf() as s:
        seeded = await seeded_year_with_units(s, year=year, n_units=1)
        s.add_all(_seeded_factors(DataEntryTypeEnum.member, year))
        await s.commit()

    unit_id = seeded.units[0].id
    crm = seeded.modules_by_unit_and_type[(unit_id, int(ModuleTypeEnum.headcount))]
    assert crm.id is not None
    crm_id: int = crm.id

    initial_ftes = [1.0, 0.5]
    initial_rows = [
        {
            "name": f"Member {i}",
            "user_institutional_id": f"M-{i:03d}",
            "fte": fte,
            "position_category": "professor",
        }
        for i, fte in enumerate(initial_ftes, start=1)
    ]

    csv_path = csv_fixture_path("headcount", "data")
    initial_provider = _make_writing_csv_provider(
        module_id=crm_id,
        data_entry_type=DataEntryTypeEnum.member,
        rows=initial_rows,
    )
    parent_v1, _children_v1 = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=year,
        ingestion_method=IngestionMethod.csv,
        provider_class=initial_provider,
    )
    assert parent_v1.state == IngestionState.FINISHED

    food_leaf_id = EmissionType.food__vegetarian.value
    expected_v1_food = sum(_expected_kg_per_leaf(f)[food_leaf_id] for f in initial_ftes)
    async with Sf() as s:
        await assert_stats_match(
            s,
            crm_id,
            {
                "by_emission_type": {
                    str(food_leaf_id): pytest.approx(expected_v1_food, rel=1e-6),
                },
            },
        )

    # ── Reupload: mutate the existing entries' FTEs, dispatch a no-op
    #    ingest stub, and assert the chain refreshes stats.
    #
    # Production endpoints flip the previous parent's ``is_current=False``
    # before inserting a new one (see
    # ``DataIngestionRepository.create_csv_ingest_job``); the partial
    # unique index ``ix_data_ingestion_jobs_is_current_unique`` enforces
    # at-most-one current job per (module, det, target, method, year).
    # ``dispatch_csv_and_wait`` doesn't model that flip, so do it
    # ourselves — without this the second insert raises a
    # UniqueViolation.
    new_ftes = [0.6, 0.3]
    async with Sf() as s:
        prev_parent = await s.get(DataIngestionJob, parent_v1.id)
        assert prev_parent is not None
        prev_parent.is_current = False
        s.add(prev_parent)

        entries = (
            (
                await s.execute(
                    select(DataEntry).where(
                        col(DataEntry.carbon_report_module_id) == crm_id
                    )
                )
            )
            .scalars()
            .all()
        )
        # Stable ordering by id matches insertion order.
        entries.sort(key=lambda e: e.id or 0)
        assert len(entries) == len(new_ftes)
        for entry, new_fte in zip(entries, new_ftes):
            updated = dict(entry.data)
            updated["fte"] = new_fte
            entry.data = updated
            s.add(entry)
        await s.commit()

    # Use a no-op provider for the reupload; the data is already on disk
    # via the mutate-in-place step above.  The chain's
    # emission_recalc → aggregation children still fire and rebuild
    # ``data_entry_emissions`` + ``stats`` from the new entry data.
    noop_provider = MagicMock()
    noop_provider.set_job_id = AsyncMock()
    noop_provider.ingest = AsyncMock(
        return_value={
            "status_message": "noop",
            "data": {"result": IngestionResult.SUCCESS, "inserted": 0},
        }
    )

    class NoopProvider:
        def __new__(cls, *args, **kwargs):
            return noop_provider

    parent_v2, _children_v2 = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=csv_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.headcount),
        data_entry_type_id=int(DataEntryTypeEnum.member),
        year=year,
        ingestion_method=IngestionMethod.csv,
        provider_class=NoopProvider,
    )
    assert parent_v2.state == IngestionState.FINISHED

    expected_v2_by_leaf: dict[int, float] = {
        emission.value: 0.0 for _, _, emission, _, _ in _HEADCOUNT_LEAVES
    }
    for fte in new_ftes:
        for leaf_id, kg in _expected_kg_per_leaf(fte).items():
            expected_v2_by_leaf[leaf_id] += kg
    expected_v2_total = sum(expected_v2_by_leaf.values())

    assert expected_v2_by_leaf[food_leaf_id] != pytest.approx(
        expected_v1_food, rel=1e-6
    ), (
        "test design: the new FTE list must produce a different food total "
        "than the initial list — otherwise the assertion below trivially "
        "passes regardless of recompute behavior"
    )

    async with Sf() as s:
        await assert_stats_match(
            s,
            crm_id,
            {
                "by_emission_type": {
                    str(leaf_id): pytest.approx(kg, rel=1e-6)
                    for leaf_id, kg in expected_v2_by_leaf.items()
                },
                "total": pytest.approx(expected_v2_total, rel=1e-6),
            },
        )

    await engine.dispose()
