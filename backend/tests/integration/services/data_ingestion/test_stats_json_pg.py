"""Cross-cutting regression gate: pin the JSON shape of
``carbon_report_modules.stats`` and ``carbon_reports.stats`` (Plan 310
test-coverage batch, Unit 9/11).

Goal
----
A future bug that breaks aggregation should land here first.  This file
asserts:

1. Per-module stats shape — every ``ModuleTypeEnum`` writes (or for the
   ``research_facilities`` exception leaves) a stats dict whose
   top-level keys match the contract emitted by
   ``compute_module_stats``.
2. Per-module stats math — for three modules with hand-computed seeds
   (one cross-root, one Strategy-A flat, one Strategy-B nested) the
   ``scope1/2/3``, ``total``, ``by_emission_type`` (leaves + rollups),
   and ``entry_count`` values match exactly.
3. Cross-module rollup — ``carbon_reports.stats`` rolls up across
   modules and units to ``sum(crm.stats.total)`` plus the extras
   ``recompute_report_stats`` adds: ``it_total_kg`` and
   ``highest_category_module_id`` (None unless a module is VALIDATED).

Why this skips the CSV path
---------------------------
The CSV → emission_recalc → aggregation chain is already exercised by
``test_full_dag_pipeline_pg.py`` (chain wiring) and the Strategy A/B
rematch tests.  Going through CSV here adds factor + provider plumbing
that obscures the math we're trying to pin.  Instead we seed
``DataEntry`` + ``DataEntryEmission`` rows directly and call
``recompute_stats`` on the service — that's the single funnel through
which both the per-module and per-report stats are written, so a bug
in either lands here.

Pragmatic coverage (per the unit's spec)
----------------------------------------
- 3 modules with hand-computed math:
    * ``headcount`` — multi-root (food + waste + commuting), exercises
      cross-root scope3 totals.
    * ``equipment`` — single root, single leaf
      (Strategy-A flat shape).
    * ``professional_travel`` — single root, multi-level rollup (leaf
      → train/plane → professional_travel) which validates that
      intermediate non-leaf nodes are populated by the rollup loop.
- All 8 modules parametrised for shape-only assertions (key set +
  type), with a special ``research_facilities`` branch that pins
  "stats stays None" — that module has no
  ``MODULE_TYPE_TO_EMISSION_ROOTS`` entry so ``recompute_stats``
  returns early (line 282-285 of carbon_report_module_service).
- One cross-module rollup test: 2 units, 3 different modules, status
  flip on one to validate ``highest_category_module_id``.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from typing import Optional

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select as sm_select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.module_type import (
    ModuleTypeEnum,
)
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.carbon_report_service import CarbonReportService
from app.utils.it_breakdown import IT_EMISSION_TYPES

from .conftest import seeded_year_with_units

# ---------------------------------------------------------------------------
# Tiny seed helpers — keep the test math obvious by working in round
# numbers (100, 60, 40) so any arithmetic mistake surfaces immediately.
# ---------------------------------------------------------------------------


async def _seed_emission(
    session: AsyncSession,
    *,
    crm_id: int,
    data_entry_type: DataEntryTypeEnum,
    emission_type: EmissionType,
    kg_co2eq: float,
    additional_value: Optional[float] = None,
) -> DataEntry:
    """Insert one ``DataEntry`` + one ``DataEntryEmission`` leaf row.

    Returns the entry so the caller can chain more emissions onto it
    (some ``DataEntry`` rows produce N emissions in production).
    """
    entry = DataEntry(
        data_entry_type_id=int(data_entry_type),
        carbon_report_module_id=crm_id,
        data={},
    )
    session.add(entry)
    await session.flush()

    em = DataEntryEmission(
        data_entry_id=entry.id,
        emission_type_id=int(emission_type),
        kg_co2eq=kg_co2eq,
        additional_value=additional_value,
        scope=int(emission_type.scope) if emission_type.scope is not None else None,
        meta={},
    )
    session.add(em)
    await session.flush()
    return entry


# ---------------------------------------------------------------------------
# Fixtures — one seeded year per test.  Function-scoped: each test
# starts from a fresh schema (``pg_dsn`` drops + recreates) so
# inter-test pollution is structurally impossible.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded(pg_dsn):
    """Fresh schema + 1 year + 1 unit + every module's CRM row.

    Yields ``(seeded, session_factory, engine)`` so tests can open
    their own sessions and dispose the engine cleanly.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        seed = await seeded_year_with_units(s, year=2025, n_units=1)

    yield seed, Sf

    await engine.dispose()


# ===========================================================================
# 1. Shape contract — parametrised across all 8 modules
# ===========================================================================


# Top-level keys ``compute_module_stats`` writes.  Pinned here so a
# future PR that drops a key (or renames one) trips this assertion
# rather than silently breaking the frontend.  See
# ``app/services/carbon_report_module_service.py::compute_module_stats``.
EXPECTED_MODULE_STATS_KEYS: set[str] = {
    "scope1",
    "scope2",
    "scope3",
    "total",
    "by_emission_type",
    "by_additional_value",
    "computed_at",
    "entry_count",
}


# (module_type, data_entry_type, emission_type) — one shape probe per
# module.  Picks a leaf the runtime resolver can't accidentally drop
# (no ambiguous gas/cabin keys).
_MODULE_SHAPE_PROBES: list[tuple[ModuleTypeEnum, DataEntryTypeEnum, EmissionType]] = [
    (
        ModuleTypeEnum.headcount,
        DataEntryTypeEnum.member,
        EmissionType.food__non_vegetarian,
    ),
    (
        ModuleTypeEnum.professional_travel,
        DataEntryTypeEnum.plane,
        EmissionType.professional_travel__plane__eco,
    ),
    (
        ModuleTypeEnum.buildings,
        DataEntryTypeEnum.energy_combustion,
        EmissionType.buildings__combustion__natural_gas,
    ),
    (
        ModuleTypeEnum.equipment,
        DataEntryTypeEnum.it,
        EmissionType.equipment__it,
    ),
    (
        ModuleTypeEnum.purchase,
        DataEntryTypeEnum.it_equipment,
        EmissionType.purchases__it_equipment,
    ),
    (
        ModuleTypeEnum.process_emissions,
        DataEntryTypeEnum.process_emissions,
        EmissionType.process_emissions__co2,
    ),
    (
        ModuleTypeEnum.external_cloud_and_ai,
        DataEntryTypeEnum.external_clouds,
        EmissionType.external__clouds__calcul,
    ),
    (
        ModuleTypeEnum.research_facilities,
        DataEntryTypeEnum.research_facilities,
        EmissionType.research_facilities__facilities,
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module_type,data_entry_type,emission_type",
    _MODULE_SHAPE_PROBES,
    ids=[mt.name for mt, _, _ in _MODULE_SHAPE_PROBES],
)
async def test_module_stats_shape_pins_top_level_keys(
    seeded,
    module_type: ModuleTypeEnum,
    data_entry_type: DataEntryTypeEnum,
    emission_type: EmissionType,
) -> None:
    """Every mapped module writes a stats dict with the canonical key
    set.  A future drop/rename surfaces here as ``missing keys`` or
    ``extra keys``.

    The arithmetic is asserted in the dedicated math tests below; this
    one only pins the dict's outermost shape so it stays cheap and
    fast for all 7 mapped modules.
    """
    seed, Sf = seeded
    unit_id = seed.units[0].id
    crm = seed.modules_by_unit_and_type[(unit_id, int(module_type))]

    async with Sf() as s:
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=data_entry_type,
            emission_type=emission_type,
            kg_co2eq=100.0,
        )
        await s.commit()

    async with Sf() as s:
        svc = CarbonReportModuleService(s)
        await svc.recompute_stats(crm.id)
        await s.commit()

    async with Sf() as s:
        fresh = await s.get(CarbonReportModule, crm.id)
        assert fresh is not None
        stats = fresh.stats
        assert isinstance(stats, dict), (
            f"{module_type.name}: stats must be a dict, got {type(stats)!r}"
        )
        assert set(stats.keys()) == EXPECTED_MODULE_STATS_KEYS, (
            f"{module_type.name}: top-level keys mismatch.\n"
            f"  expected: {sorted(EXPECTED_MODULE_STATS_KEYS)}\n"
            f"  actual:   {sorted(stats.keys())}\n"
            f"  missing:  {sorted(EXPECTED_MODULE_STATS_KEYS - set(stats.keys()))}\n"
            f"  extra:    {sorted(set(stats.keys()) - EXPECTED_MODULE_STATS_KEYS)}"
        )

        # Type pins — silent type drift (e.g. dict→str on
        # ``by_emission_type``) is exactly what the frontend can't
        # tolerate but nothing else would catch.
        assert isinstance(stats["scope1"], (int, float))
        assert isinstance(stats["scope2"], (int, float))
        assert isinstance(stats["scope3"], (int, float))
        assert isinstance(stats["total"], (int, float))
        assert isinstance(stats["by_emission_type"], dict)
        assert isinstance(stats["by_additional_value"], dict)
        assert isinstance(stats["computed_at"], str)
        assert isinstance(stats["entry_count"], int)


@pytest.mark.asyncio
async def test_research_facilities_stats_math_two_leaves_one_root_scope3(
    seeded,
) -> None:
    """``research_facilities`` rolls two leaf-level emissions under one root.

    Seeds ``research_facilities__facilities`` (100.0) and the actual leaf
    ``research_facilities__animal__mice`` (40.0) — the mice type was added as a
    child of ``research_facilities__animal`` in the subcategory correction commit,
    making the bare ``research_facilities__animal`` an intermediate rollup node.
    The leaf path is the production-correct flow from ``_resolve_animal_facilities``.

    Seeding both leaves pins:
      - ``scope3 == sum of leaves`` (100+40=140)
      - ``scope1`` and ``scope2`` stay 0
      - ``by_emission_type`` contains the two leaves, the animal rollup, AND root rollup
      - ``entry_count`` matches the number of ``DataEntry`` rows
    """
    seed, Sf = seeded
    unit_id = seed.units[0].id
    crm = seed.modules_by_unit_and_type[
        (unit_id, int(ModuleTypeEnum.research_facilities))
    ]

    async with Sf() as s:
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=DataEntryTypeEnum.research_facilities,
            emission_type=EmissionType.research_facilities__facilities,
            kg_co2eq=100.0,
        )
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=DataEntryTypeEnum.mice_and_fish_animal_facilities,
            emission_type=EmissionType.research_facilities__animal__mice,
            kg_co2eq=40.0,
        )
        await s.commit()

    async with Sf() as s:
        svc = CarbonReportModuleService(s)
        await svc.recompute_stats(crm.id)
        await s.commit()

    async with Sf() as s:
        fresh = await s.get(CarbonReportModule, crm.id)
        assert fresh is not None
        stats = fresh.stats
        assert stats is not None, (
            "research_facilities now has a MODULE_TYPE_TO_EMISSION_ROOTS entry; "
            "recompute_stats must produce stats. Got None."
        )

        assert stats["scope1"] == 0.0
        assert stats["scope2"] == 0.0
        assert stats["scope3"] == 140.0, (
            f"scope3 should be 100+40=140; got {stats['scope3']}"
        )
        assert stats["total"] == 140.0
        assert stats["entry_count"] == 2

        by_et = stats["by_emission_type"]
        assert by_et[str(int(EmissionType.research_facilities__facilities))] == 100.0
        assert by_et[str(int(EmissionType.research_facilities__animal__mice))] == 40.0
        # Intermediate rollup: mice leaf rolls up to animal (40.0)
        assert by_et[str(int(EmissionType.research_facilities__animal))] == 40.0
        # Root rollup: facilities (100) + mice via animal (40) = 140
        assert by_et[str(int(EmissionType.research_facilities))] == 140.0


# ===========================================================================
# 2. Math contracts — three modules, hand-computed expectations
# ===========================================================================


@pytest.mark.asyncio
async def test_headcount_stats_math_cross_root_scope3(seeded) -> None:
    """Headcount has 3 emission roots (food, waste, commuting), all
    scope 3.  Seeding one leaf under each root pins:

      - ``scope3 == sum of all three leaves``
      - ``scope1`` and ``scope2`` stay 0
      - ``total == scope3``
      - ``by_emission_type`` contains both leaves AND their root-level
        rollups (food, waste, commuting roots populated by the rollup
        loop in ``compute_module_stats`` lines 73-83)
      - ``entry_count`` matches the number of ``DataEntry`` rows, NOT
        the number of emission rows
    """
    seed, Sf = seeded
    unit_id = seed.units[0].id
    crm = seed.modules_by_unit_and_type[(unit_id, int(ModuleTypeEnum.headcount))]

    # 3 entries × 1 emission each → entry_count = 3
    async with Sf() as s:
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=DataEntryTypeEnum.member,
            emission_type=EmissionType.food__non_vegetarian,
            kg_co2eq=100.0,
        )
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=DataEntryTypeEnum.member,
            emission_type=EmissionType.waste__incineration,
            kg_co2eq=60.0,
        )
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=DataEntryTypeEnum.member,
            emission_type=EmissionType.commuting__car,
            kg_co2eq=40.0,
        )
        await s.commit()

    async with Sf() as s:
        svc = CarbonReportModuleService(s)
        await svc.recompute_stats(crm.id)
        await s.commit()

    async with Sf() as s:
        fresh = await s.get(CarbonReportModule, crm.id)
        assert fresh is not None
        stats = fresh.stats
        assert stats is not None

        assert stats["scope1"] == 0.0, f"scope1 should be 0; got {stats['scope1']}"
        assert stats["scope2"] == 0.0, f"scope2 should be 0; got {stats['scope2']}"
        assert stats["scope3"] == 200.0, (
            f"scope3 should be 100+60+40=200; got {stats['scope3']}"
        )
        assert stats["total"] == 200.0
        assert stats["entry_count"] == 3

        by_et = stats["by_emission_type"]
        # Leaves (keys are str(emission_type_id))
        assert by_et[str(int(EmissionType.food__non_vegetarian))] == 100.0
        assert by_et[str(int(EmissionType.waste__incineration))] == 60.0
        assert by_et[str(int(EmissionType.commuting__car))] == 40.0
        # Root-level rollups (each root's subtree includes only one
        # seeded leaf, so the rollup equals that leaf)
        assert by_et[str(int(EmissionType.food))] == 100.0
        assert by_et[str(int(EmissionType.waste))] == 60.0
        assert by_et[str(int(EmissionType.commuting))] == 40.0


@pytest.mark.asyncio
async def test_equipment_stats_math_single_root_scope2(seeded) -> None:
    """Equipment has one root (``equipment``) with three leaves
    (scientific / it / other), all scope 2.  Seeding two leaves pins:

      - ``scope2 == sum of leaves``
      - ``total == scope2``
      - root-level rollup ``equipment`` equals the sum of its leaves
        (proves the rollup loop, not just the leaf write)
    """
    seed, Sf = seeded
    unit_id = seed.units[0].id
    crm = seed.modules_by_unit_and_type[(unit_id, int(ModuleTypeEnum.equipment))]

    async with Sf() as s:
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=DataEntryTypeEnum.it,
            emission_type=EmissionType.equipment__it,
            kg_co2eq=60.0,
        )
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=DataEntryTypeEnum.scientific,
            emission_type=EmissionType.equipment__scientific,
            kg_co2eq=40.0,
        )
        await s.commit()

    async with Sf() as s:
        svc = CarbonReportModuleService(s)
        await svc.recompute_stats(crm.id)
        await s.commit()

    async with Sf() as s:
        fresh = await s.get(CarbonReportModule, crm.id)
        assert fresh is not None
        stats = fresh.stats
        assert stats is not None

        assert stats["scope1"] == 0.0
        assert stats["scope2"] == 100.0, f"scope2 should be 60+40=100; got {stats}"
        assert stats["scope3"] == 0.0
        assert stats["total"] == 100.0
        assert stats["entry_count"] == 2

        by_et = stats["by_emission_type"]
        assert by_et[str(int(EmissionType.equipment__it))] == 60.0
        assert by_et[str(int(EmissionType.equipment__scientific))] == 40.0
        # Rollup: equipment root sums all subtree leaves
        assert by_et[str(int(EmissionType.equipment))] == 100.0


@pytest.mark.asyncio
async def test_professional_travel_stats_math_multi_level_rollup(seeded) -> None:
    """Professional travel has 3 levels: leaf (cabin/class) → mode
    (train/plane) → root (professional_travel).  Seeding one leaf
    under each mode pins the rollup-of-rollups behaviour:

      - leaf level: each cabin gets its own kg_co2eq
      - mid level: ``professional_travel__train`` / ``__plane`` sum
        their respective subtrees
      - root level: ``professional_travel`` sums everything

    A bug that walks only one level deep would surface here as a
    missing intermediate or a bad sum.
    """
    seed, Sf = seeded
    unit_id = seed.units[0].id
    crm = seed.modules_by_unit_and_type[
        (unit_id, int(ModuleTypeEnum.professional_travel))
    ]

    async with Sf() as s:
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=DataEntryTypeEnum.plane,
            emission_type=EmissionType.professional_travel__plane__eco,
            kg_co2eq=60.0,
            additional_value=1000.0,
        )
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=DataEntryTypeEnum.train,
            emission_type=EmissionType.professional_travel__train__class_2,
            kg_co2eq=40.0,
            additional_value=200.0,
        )
        await s.commit()

    async with Sf() as s:
        svc = CarbonReportModuleService(s)
        await svc.recompute_stats(crm.id)
        await s.commit()

    async with Sf() as s:
        fresh = await s.get(CarbonReportModule, crm.id)
        assert fresh is not None
        stats = fresh.stats
        assert stats is not None

        assert stats["scope3"] == 100.0
        assert stats["total"] == 100.0
        assert stats["entry_count"] == 2

        by_et = stats["by_emission_type"]
        # Leaves
        assert by_et[str(int(EmissionType.professional_travel__plane__eco))] == 60.0
        assert by_et[str(int(EmissionType.professional_travel__train__class_2))] == 40.0
        # Mid-level rollups
        assert by_et[str(int(EmissionType.professional_travel__plane))] == 60.0
        assert by_et[str(int(EmissionType.professional_travel__train))] == 40.0
        # Root rollup — sums both modes
        assert by_et[str(int(EmissionType.professional_travel))] == 100.0

        # additional_value rolls up the same way (km-equivalent)
        by_add = stats["by_additional_value"]
        assert by_add[str(int(EmissionType.professional_travel__plane__eco))] == 1000.0
        assert (
            by_add[str(int(EmissionType.professional_travel__train__class_2))] == 200.0
        )
        assert by_add[str(int(EmissionType.professional_travel))] == 1200.0


# ===========================================================================
# 3. Cross-module rollup — carbon_reports.stats
# ===========================================================================


@pytest.mark.asyncio
async def test_report_stats_rollup_sums_modules_and_adds_it_total(seeded) -> None:
    """``carbon_reports.stats`` rolls up across all child modules.  This
    test seeds three different modules so the rollup has to traverse
    different scope/category contributions and assert:

      - ``scope1/2/3`` sum across modules
      - ``total == sum(crm.stats.total)``
      - ``it_total_kg`` equals the subset of ``by_emission_type``
        whose keys are in ``IT_EMISSION_TYPES`` (verified via
        ``app.utils.it_breakdown.IT_EMISSION_TYPES``)
      - ``highest_category_module_id`` is None when no module is
        VALIDATED (default after seeding)
      - flipping one module to VALIDATED makes it the
        ``highest_category_module_id`` (largest validated total wins)
      - ``entry_count`` sums per-module entry counts
    """
    seed, Sf = seeded
    unit_id = seed.units[0].id
    eq_crm = seed.modules_by_unit_and_type[(unit_id, int(ModuleTypeEnum.equipment))]
    purchase_crm = seed.modules_by_unit_and_type[
        (unit_id, int(ModuleTypeEnum.purchase))
    ]
    proc_crm = seed.modules_by_unit_and_type[
        (unit_id, int(ModuleTypeEnum.process_emissions))
    ]
    report = seed.reports_by_unit[unit_id]

    # Seed:
    #   - equipment__it (scope 2, IT)            : 60.0
    #   - purchases__it_equipment (scope 3, IT)  : 40.0
    #   - process_emissions__co2 (scope 1, non-IT): 100.0
    # Expected report rollup:
    #   scope1 = 100.0, scope2 = 60.0, scope3 = 40.0, total = 200.0
    #   it_total_kg = 60 + 40 = 100.0  (process_emissions excluded)
    #   entry_count = 3
    async with Sf() as s:
        await _seed_emission(
            s,
            crm_id=eq_crm.id,
            data_entry_type=DataEntryTypeEnum.it,
            emission_type=EmissionType.equipment__it,
            kg_co2eq=60.0,
        )
        await _seed_emission(
            s,
            crm_id=purchase_crm.id,
            data_entry_type=DataEntryTypeEnum.it_equipment,
            emission_type=EmissionType.purchases__it_equipment,
            kg_co2eq=40.0,
        )
        await _seed_emission(
            s,
            crm_id=proc_crm.id,
            data_entry_type=DataEntryTypeEnum.process_emissions,
            emission_type=EmissionType.process_emissions__co2,
            kg_co2eq=100.0,
        )
        await s.commit()

    # Recompute every module so each call's recompute_report_stats
    # invocation rolls up the latest module set.
    async with Sf() as s:
        svc = CarbonReportModuleService(s)
        await svc.recompute_stats(eq_crm.id)
        await svc.recompute_stats(purchase_crm.id)
        await svc.recompute_stats(proc_crm.id)
        await s.commit()

    # First inspection: no module is VALIDATED, so
    # highest_category_module_id stays None.
    async with Sf() as s:
        fresh_report = await s.get(CarbonReport, report.id)
        assert fresh_report is not None
        stats = fresh_report.stats
        assert stats is not None, "carbon_reports.stats must be populated"

        assert stats["scope1"] == 100.0, stats
        assert stats["scope2"] == 60.0
        assert stats["scope3"] == 40.0
        assert stats["total"] == 200.0
        assert stats["entry_count"] == 3

        # Rollup formula: report.total must equal sum of module totals.
        res = await s.execute(
            sm_select(CarbonReportModule).where(
                CarbonReportModule.carbon_report_id == report.id
            )
        )
        modules = list(res.scalars().all())
        modules_total = sum((m.stats or {}).get("total", 0.0) or 0.0 for m in modules)
        assert stats["total"] == modules_total, (
            f"report.total ({stats['total']}) must equal "
            f"sum(crm.stats.total) ({modules_total})"
        )

        # it_total_kg: subset of by_emission_type whose keys are in
        # IT_EMISSION_TYPES.  A future change to the IT set will trip
        # both this independent recompute and the build math.
        it_keys = {str(et.value) for et in IT_EMISSION_TYPES}
        expected_it_total = sum(
            v for k, v in stats["by_emission_type"].items() if k in it_keys
        )
        assert stats["it_total_kg"] == expected_it_total, (
            f"it_total_kg mismatch: stats={stats['it_total_kg']}, "
            f"recomputed={expected_it_total}"
        )
        assert stats["it_total_kg"] == 100.0

        assert stats["highest_category_module_id"] is None, (
            f"no validated modules → highest_category_module_id should be None; "
            f"got {stats['highest_category_module_id']!r}"
        )

    # Second inspection: validate process_emissions (largest total at
    # 100.0); the report rollup must surface it as the highest category.
    # recompute_stats now resets a module to IN_PROGRESS (data changed →
    # validation is stale), so validate first, then drive the report-level
    # rollup directly to assert highest-category derivation from a validated
    # module.
    async with Sf() as s:
        fresh_proc = await s.get(CarbonReportModule, proc_crm.id)
        assert fresh_proc is not None
        fresh_proc.status = ModuleStatus.VALIDATED
        s.add(fresh_proc)
        await s.flush()
        await CarbonReportService(s).recompute_report_stats(report.id)
        await s.commit()

    async with Sf() as s:
        fresh_report = await s.get(CarbonReport, report.id)
        assert fresh_report is not None
        stats = fresh_report.stats
        assert stats is not None
        assert stats["highest_category_module_id"] == int(
            ModuleTypeEnum.process_emissions
        ), (
            "process_emissions is the highest validated total (100.0); "
            f"expected highest_category_module_id="
            f"{int(ModuleTypeEnum.process_emissions)}; "
            f"got {stats['highest_category_module_id']!r}"
        )


# ===========================================================================
# 4. Status bump — recompute marks a module IN_PROGRESS
# ===========================================================================


@pytest.mark.asyncio
async def test_recompute_stats_marks_module_in_progress(seeded) -> None:
    """A single recompute flips the module to IN_PROGRESS, even from a
    previously VALIDATED state — recomputed numbers make any prior
    validation stale (the bug: modules with data still read NOT_STARTED).
    """
    seed, Sf = seeded
    unit_id = seed.units[0].id
    crm = seed.modules_by_unit_and_type[
        (unit_id, int(ModuleTypeEnum.process_emissions))
    ]

    async with Sf() as s:
        await _seed_emission(
            s,
            crm_id=crm.id,
            data_entry_type=DataEntryTypeEnum.process_emissions,
            emission_type=EmissionType.process_emissions__co2,
            kg_co2eq=100.0,
        )
        # Pre-validate to prove recompute downgrades a stale validation.
        fresh = await s.get(CarbonReportModule, crm.id)
        assert fresh is not None
        fresh.status = ModuleStatus.VALIDATED
        s.add(fresh)
        await s.commit()

    async with Sf() as s:
        await CarbonReportModuleService(s).recompute_stats(crm.id)
        await s.commit()

    async with Sf() as s:
        fresh = await s.get(CarbonReportModule, crm.id)
        assert fresh is not None
        assert fresh.status == ModuleStatus.IN_PROGRESS, (
            f"recompute_stats must mark the module IN_PROGRESS; "
            f"got {ModuleStatus(fresh.status).name}"
        )


@pytest.mark.asyncio
async def test_recompute_stats_many_marks_all_modules_in_progress(seeded) -> None:
    """The batch path bumps every refreshed module to IN_PROGRESS in one call."""
    seed, Sf = seeded
    unit_id = seed.units[0].id
    eq_crm = seed.modules_by_unit_and_type[(unit_id, int(ModuleTypeEnum.equipment))]
    proc_crm = seed.modules_by_unit_and_type[
        (unit_id, int(ModuleTypeEnum.process_emissions))
    ]

    async with Sf() as s:
        await _seed_emission(
            s,
            crm_id=eq_crm.id,
            data_entry_type=DataEntryTypeEnum.it,
            emission_type=EmissionType.equipment__it,
            kg_co2eq=60.0,
        )
        await _seed_emission(
            s,
            crm_id=proc_crm.id,
            data_entry_type=DataEntryTypeEnum.process_emissions,
            emission_type=EmissionType.process_emissions__co2,
            kg_co2eq=100.0,
        )
        await s.commit()

    async with Sf() as s:
        refreshed = await CarbonReportModuleService(s).recompute_stats_many(
            [eq_crm.id, proc_crm.id]
        )
        await s.commit()
        assert refreshed == 2

    async with Sf() as s:
        for crm_id in (eq_crm.id, proc_crm.id):
            fresh = await s.get(CarbonReportModule, crm_id)
            assert fresh is not None
            assert fresh.status == ModuleStatus.IN_PROGRESS
