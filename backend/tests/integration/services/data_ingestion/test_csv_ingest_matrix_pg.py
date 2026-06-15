"""Standard-modules CSV ingest matrix (Plan 310 test-coverage, Unit 2/11).

Covers the CSV ingest path for the five ``MODULE_PER_YEAR`` modules
that route through the **plain** ``ModulePerYearCSVProvider`` and key
emissions on ``primary_factor_id``:

* ``equipment``
* ``purchase``
* ``external_cloud_and_ai``
* ``process_emissions``
* ``research_facilities``

Buildings + travel are out of scope (separate units own them).

Each test is one falsifiable hypothesis under the cartesian product
``(module, factors_state)``:

1. After ``dispatch_csv_and_wait`` finishes the chain, every persisted
   ``DataEntry`` row has ``source = CSV_MODULE_PER_YEAR`` (the
   provider's ``_get_source_from_entity_type`` pin).
2. With factors pre-loaded → ``data_entry_emissions`` rows exist with
   ``kg_co2eq`` matching the factor formula.
3. Without factors → fail-fast: parent reaches FINISHED+ERROR with a
   single-line ``status_message`` naming the missing-factor cause, no
   children are dispatched, and no DataEntry/emissions/stats are
   written.  Replaces the older "absent factors → graceful FINISHED+
   SUCCESS, no emissions" contract retired by #1236 (commit 503bfe5b
   added ``_guard_factors_required`` + the ``_FACTOR_INFERRED_MODULES``
   short-circuit so the operator sees one explanation rather than
   50 000 row-level "no matching factor" errors).
4. The targeted module's CRM has a dict-shaped ``stats`` payload
   for module types that appear in ``MODULE_TYPE_TO_EMISSION_ROOTS``
   (proves the aggregation chain committed); for module types
   absent from that map (research_facilities today — its emission
   tree lives elsewhere) the chain still drives to FINISHED but
   ``recompute_stats`` early-returns, so we pin ``stats is None``
   instead.  Either branch proves the chain wired through.
5. No chain leakage: a sibling unit's CRM for the SAME module type
   has zero ``DataEntry`` rows (a single-unit upload must not write
   under any other unit's modules).  Stats on the sibling CRM are
   not pinned because aggregation runs at the ``(module_type, year)``
   slice and may legitimately recompute the sibling's empty-state
   payload — the entries-count discriminator is what falsifies a
   real cross-unit leak.

The tests use the real ``ModulePerYearCSVProvider`` so we exercise
actual CSV parsing, factor lookup, and the ``BULK_PATH_PURE_ASYNC``
chain-ownership contract.  ``files_store`` is faked via a patch on
``make_files_store`` — the provider's lazy-init property reads from
that import every time, so a single patch covers both the move-from-
source and move-to-processed legs.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReportModule
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.data_ingestion import (
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.models.module_type import MODULE_TYPE_TO_EMISSION_ROOTS, ModuleTypeEnum
from app.services.data_ingestion.provider_factory import ProviderFactory

from .conftest import (
    assert_stats_match,
    csv_fixture_path,
    dispatch_csv_and_wait,
    seeded_year_with_units,
)

# ---------------------------------------------------------------------------
# Test matrix specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ModuleSpec:
    """Per-module knobs for the CSV-ingest matrix.

    ``data_entry_type`` is pinned on every parent job: without it,
    ``ModulePerYearCSVProvider._resolve_handler_and_validate`` falls
    back to factor-based det inference (Priority 3), which fails when
    factors are absent and drives ``rows_processed=0`` →
    ``IngestionResult.ERROR`` → ``csv_ingest_handler`` skips the chain
    fan-out (``ingestion_tasks.py`` lines 63-66).  Assertion 3 would
    then hold for the wrong reason (no rows persisted vs no factors
    matched).

    ``csv_module`` is the registered key in
    ``conftest._TRIMMED_CSV_FIXTURES``.  ``factor_classification``
    must carry whatever the handler's ``kind_field`` (and optional
    ``subkind_field``) look up.  ``expected_kg_first_row`` is the
    handler formula's output for the first trimmed-CSV row given the
    seeded factor — used by assertion 2.
    """

    module_type: ModuleTypeEnum
    data_entry_type: DataEntryTypeEnum
    csv_module: str
    emission_type: EmissionType
    factor_classification: dict[str, Any]
    factor_values: dict[str, Any]
    expected_kg_first_row: float


# Per-module specs.  Choices intentionally mirror
# ``test_strategy_a_rematch_pg.py`` so factor shape + formula expectations
# align with code that's already been bot-triaged.
_SPECS: dict[str, _ModuleSpec] = {
    "process_emissions": _ModuleSpec(
        module_type=ModuleTypeEnum.process_emissions,
        data_entry_type=DataEntryTypeEnum.process_emissions,
        csv_module="processemissions",
        emission_type=EmissionType.process_emissions__co2,
        factor_classification={"category": "co2", "subcategory": "industrial"},
        factor_values={"ef_kg_co2eq_per_unit": 1.5, "unit": "kg"},
        # Row 1: quantity=100.0, ef=1.5 → 150.0 kg.
        expected_kg_first_row=150.0,
    ),
    "equipment": _ModuleSpec(
        module_type=ModuleTypeEnum.equipment,
        data_entry_type=DataEntryTypeEnum.it,
        csv_module="equipments",
        emission_type=EmissionType.equipment__it,
        factor_classification={
            "equipment_class": "Laptop",
            "sub_class": "Standard",
            "year": 2025,
        },
        factor_values={
            "active_power_w": 100.0,
            "standby_power_w": 10.0,
            "ef_kg_co2eq_per_kwh": 0.1,
        },
        # weekly_wh = 40*100 + 128*10 = 5280 Wh.
        # annual_kwh = 5280 * WEEKS_PER_YEAR / 1000.  Default
        # WEEKS_PER_YEAR=52 → 274.56 kWh; * ef=0.1 → 27.456.
        expected_kg_first_row=27.456,
    ),
    "external_cloud_and_ai": _ModuleSpec(
        module_type=ModuleTypeEnum.external_cloud_and_ai,
        data_entry_type=DataEntryTypeEnum.external_clouds,
        csv_module="external_clouds",
        emission_type=EmissionType.external__clouds__calcul,
        factor_classification={
            "provider": "AWS",
            "service_type": "compute",
            "currency": "eur",
        },
        factor_values={"ef_kg_co2eq_per_currency": 0.05, "currency": "eur"},
        # Row 1: spent_amount=200.0, ef=0.05 → 10.0 (eur=eur, no FX).
        expected_kg_first_row=10.0,
    ),
    "purchase": _ModuleSpec(
        module_type=ModuleTypeEnum.purchase,
        data_entry_type=DataEntryTypeEnum.it_equipment,
        csv_module="purchases_common",
        emission_type=EmissionType.purchases__it_equipment,
        factor_classification={"purchase_institutional_code": "PIC-IT"},
        factor_values={"ef_kg_co2eq_per_currency": 0.5, "currency": "eur"},
        # Row 1: total_spent_amount=200.0, ef=0.5 → 100.0 (eur=eur).
        expected_kg_first_row=100.0,
    ),
    "research_facilities": _ModuleSpec(
        module_type=ModuleTypeEnum.research_facilities,
        data_entry_type=DataEntryTypeEnum.research_facilities,
        csv_module="researchfacilities_common",
        emission_type=EmissionType.research_facilities__facilities,
        factor_classification={"researchfacility_id": "RF-001"},
        factor_values={
            "use_unit": "hours",
            "total_use": 100.0,
            "kg_co2eq_sum": 1000.0,
        },
        # Row 1: use=10.0, total_use=100.0, kg_co2eq_sum=1000.0
        # → use_share=0.1, kg=100.0.
        expected_kg_first_row=100.0,
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_files_store_factory(csv_bytes: bytes):
    """Build a ``make_files_store`` replacement that returns an in-memory fake.

    The fake's two used methods are:

    * ``move_file(src, dst) -> True`` — no-op; the provider calls this
      both at setup (tmp → processing/<job_id>/) and finalize
      (processing/<job_id>/ → processed/<job_id>/).
    * ``get_file(path) -> (bytes, "text/csv")`` — ignores ``path``
      entirely and returns the rendered CSV bytes.  The provider only
      calls this once during setup; we don't track call sites.

    We return a *factory* (matching ``make_files_store``'s signature)
    rather than a singleton so each ``files_store`` property access
    inside the lazy-init path resolves to the same fake instance for a
    given test (the property memoizes after first call).
    """
    fake = MagicMock()
    fake.move_file = AsyncMock(return_value=True)
    fake.get_file = AsyncMock(return_value=(csv_bytes, "text/csv"))
    fake.file_exists = AsyncMock(return_value=True)

    def _factory():
        return fake

    return _factory


def _render_csv(template_path: Path, *, unit_institutional_id: str) -> bytes:
    """Render a trimmed-fixture template by binding the seeded unit code.

    The committed fixtures use ``{unit_institutional_id}`` as a
    placeholder so the unit-code seed (which contains a uuid suffix to
    keep cross-test isolation) can be threaded in at dispatch time.
    Returns UTF-8-encoded bytes ready to feed into the fake files_store.
    """
    template = template_path.read_text(encoding="utf-8")
    return template.format(unit_institutional_id=unit_institutional_id).encode("utf-8")


async def _write_factor(
    session: AsyncSession,
    *,
    spec: _ModuleSpec,
    year: int,
) -> int:
    """Persist the per-module ``Factor`` and return its id."""
    factor = Factor(
        emission_type_id=spec.emission_type.value,
        data_entry_type_id=spec.data_entry_type.value,
        classification=spec.factor_classification,
        values=spec.factor_values,
        year=year,
    )
    session.add(factor)
    await session.commit()
    if factor.id is None:
        raise AssertionError("Factor.id was not assigned after commit")
    return factor.id


async def _drive_csv_ingest(
    *,
    spec: _ModuleSpec,
    session_factory: async_sessionmaker[AsyncSession],
    csv_bytes: bytes,
    target_unit_id: int,
    year: int,
):
    """Patch ``make_files_store`` and dispatch the real provider chain.

    Stamps a synthetic ``file_path`` into the parent job's meta — the
    provider's ``_setup_and_validate`` calls ``move_file`` (no-op)
    then ``get_file`` (returns ``csv_bytes``) on the patched fake
    regardless of the path string, so we don't have to materialise a
    real tmp file.
    """
    provider_class = ProviderFactory.get_provider_class("ModulePerYearCSVProvider")
    if provider_class is None:
        raise AssertionError("ModulePerYearCSVProvider not registered")

    fake_factory = _make_fake_files_store_factory(csv_bytes)

    # ``make_files_store`` is imported at module level in ``base_csv_provider``;
    # patch the symbol there so the lazy property init picks up the fake.
    with patch(
        "app.services.data_ingestion.base_csv_provider.make_files_store",
        side_effect=fake_factory,
    ):
        return await dispatch_csv_and_wait(
            session_factory=session_factory,
            file_path=f"uploads/{target_unit_id}/{spec.csv_module}.csv",
            target_type=TargetType.DATA_ENTRIES,
            module_type_id=int(spec.module_type),
            data_entry_type_id=int(spec.data_entry_type),
            year=year,
            ingestion_method=IngestionMethod.csv,
            provider_class=provider_class,
        )


async def _read_data_entries(
    session: AsyncSession,
    *,
    carbon_report_module_id: int,
) -> list[DataEntry]:
    result = await session.execute(
        select(DataEntry).where(
            DataEntry.carbon_report_module_id == carbon_report_module_id
        )
    )
    return list(result.scalars().all())


async def _read_emissions_for_entries(
    session: AsyncSession,
    *,
    data_entry_ids: list[int],
) -> list[DataEntryEmission]:
    if not data_entry_ids:
        return []
    result = await session.execute(
        select(DataEntryEmission).where(
            DataEntryEmission.data_entry_id.in_(data_entry_ids)  # type: ignore[union-attr]
        )
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("module_key", list(_SPECS.keys()))
@pytest.mark.parametrize("factors_state", ["pre_loaded", "absent"])
async def test_csv_ingest_standard_module(
    pg_dsn,
    module_key: str,
    factors_state: str,
) -> None:
    """One falsifiable case per ``(module, factors_state)`` cell.

    Drives a CSV through the real ``ModulePerYearCSVProvider`` against
    a freshly-seeded carbon-report tree (2 units, every module-type
    CRM) and asserts the five contracts pinned in the module docstring.
    """
    spec = _SPECS[module_key]
    year = 2025

    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        # ── 1. Seed the carbon-report tree ────────────────────────────
        async with Sf() as s:
            seeded = await seeded_year_with_units(s, year=year, n_units=2)

        target_unit = seeded.units[0]
        sibling_unit = seeded.units[1]
        target_crm = seeded.modules_by_unit_and_type[
            (target_unit.id, int(spec.module_type))
        ]
        sibling_crm = seeded.modules_by_unit_and_type[
            (sibling_unit.id, int(spec.module_type))
        ]

        # ── 2. (Optionally) seed the factor ───────────────────────────
        if factors_state == "pre_loaded":
            async with Sf() as s:
                await _write_factor(s, spec=spec, year=year)

        # ── 3. Render the CSV with the target unit's code ─────────────
        template_path = csv_fixture_path(spec.csv_module, "data")
        csv_bytes = _render_csv(
            template_path,
            unit_institutional_id=target_unit.institutional_id,
        )

        # ── 4. Dispatch and wait for the chain to terminate ───────────
        parent, children = await _drive_csv_ingest(
            spec=spec,
            session_factory=Sf,
            csv_bytes=csv_bytes,
            target_unit_id=target_unit.id,
            year=year,
        )

        # The parent always reaches FINISHED.  For ``factors_state=absent``
        # the new fail-fast guard (#1236, commit 503bfe5b) refuses ingest
        # up-front so the result flips to ERROR with a single-line
        # status_message — the operator sees one explanation instead of
        # 50 000 row-level "no matching factor" errors.  For
        # ``pre_loaded`` we expect SUCCESS strictly.
        assert parent.state == IngestionState.FINISHED, (
            f"parent did not FINISH: state={parent.state} "
            f"status={parent.status_message}"
        )

        if factors_state == "absent":
            # Fail-fast contract: parent terminates ERROR, no children
            # are dispatched, and no DataEntry/emissions/stats are
            # written.  Pinning the absence of side-effects guards
            # against a regression where the guard misses + lets every
            # row error individually.
            assert parent.result == IngestionResult.ERROR, (
                f"factors_state=absent must trip the fail-fast guard; "
                f"got result={parent.result}, status={parent.status_message!r}"
            )
            assert "factor" in (parent.status_message or "").lower(), (
                f"absent-factors error should name the missing-factor cause; "
                f"got status_message={parent.status_message!r}"
            )
            recalc_children = [c for c in children if c.job_type == "emission_recalc"]
            assert recalc_children == [], (
                f"fail-fast must skip the chain fan-out; got recalc "
                f"children={[c.id for c in recalc_children]}"
            )

            async with Sf() as s:
                target_entries = await _read_data_entries(
                    s, carbon_report_module_id=target_crm.id
                )
            assert target_entries == [], (
                f"fail-fast must not persist DataEntry rows; got "
                f"{len(target_entries)} rows on the target CRM."
            )

            async with Sf() as s:
                sibling_entries = await _read_data_entries(
                    s, carbon_report_module_id=sibling_crm.id
                )
            assert sibling_entries == [], (
                f"sibling unit's CRM (module_type={spec.module_type.name}) "
                f"received DataEntries despite fail-fast on the target. "
                f"got {len(sibling_entries)} rows."
            )
            return

        # ── pre_loaded path ──────────────────────────────────────────
        assert parent.result == IngestionResult.SUCCESS, (
            f"parent reported {parent.result}: {parent.status_message}"
        )

        # The chain must have fanned out at least one emission_recalc
        # child (with det pinned, exactly one).  ``aggregation`` is
        # module-scoped and chained by emission_recalc; assert it ran
        # too via the dict-shaped CRM stats below.
        recalc_children = [c for c in children if c.job_type == "emission_recalc"]
        assert len(recalc_children) >= 1, (
            f"expected emission_recalc fan-out; got {[c.job_type for c in children]}"
        )

        # ── 5. Assertion 1 — every persisted DataEntry carries the
        #       CSV_MODULE_PER_YEAR source enum.
        async with Sf() as s:
            target_entries = await _read_data_entries(
                s, carbon_report_module_id=target_crm.id
            )
        assert target_entries, (
            "expected DataEntry rows on the target CRM; the trimmed CSV "
            "has 2 rows and the chain reported SUCCESS"
        )
        for entry in target_entries:
            assert entry.source == DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value, (
                f"entry id={entry.id} source={entry.source} — expected "
                f"CSV_MODULE_PER_YEAR ({DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value})"
            )

        entry_ids = [e.id for e in target_entries if e.id is not None]

        # ── 6. Assertion 2 — kg_co2eq math.
        async with Sf() as s:
            emissions = await _read_emissions_for_entries(s, data_entry_ids=entry_ids)

        assert emissions, (
            "expected data_entry_emissions when factors are pre-loaded; "
            "the recalc chain should have written one row per (entry, "
            "emission_type)"
        )
        # Pin assertion 2: at least one emission row carries the
        # formula-derived kg.  Tolerance accommodates float math
        # (process_emissions=150.0 exact; equipment uses
        # WEEKS_PER_YEAR which is float).
        kg_values = [e.kg_co2eq for e in emissions if e.kg_co2eq is not None]
        assert any(
            kg == pytest.approx(spec.expected_kg_first_row, rel=1e-2)
            for kg in kg_values
        ), (
            f"no emission row matched the expected formula output "
            f"{spec.expected_kg_first_row} (rel=1e-2); "
            f"persisted kg values: {kg_values}"
        )
        # Pin: every entry has a primary_factor_id (factor was found).
        for entry in target_entries:
            assert entry.data.get("primary_factor_id") is not None, (
                f"entry id={entry.id} missing primary_factor_id "
                f"despite factors_state=pre_loaded"
            )

        # ── 7. Assertion 4 — CRM stats committed (shape-only).
        # ``CarbonReportModuleService.recompute_stats`` early-returns
        # for module types absent from ``MODULE_TYPE_TO_EMISSION_ROOTS``
        # (research_facilities lives there today — its emission tree is
        # tracked separately).  For those modules we can't assert a
        # dict-shaped payload; instead pin that the aggregation handler
        # *ran* (chain reported SUCCESS above) and that ``stats`` stays
        # at its pre-chain value (None).  Modules WITH a roots entry
        # MUST have a dict — that's the chain's commit gate.
        has_emission_roots = spec.module_type in MODULE_TYPE_TO_EMISSION_ROOTS
        if has_emission_roots:
            async with Sf() as s:
                await assert_stats_match(s, target_crm.id, {})
        else:
            async with Sf() as s:
                fresh = await s.get(CarbonReportModule, target_crm.id)
                assert fresh is not None
                assert fresh.stats is None, (
                    f"module_type={spec.module_type.name} has no entry in "
                    f"MODULE_TYPE_TO_EMISSION_ROOTS — recompute_stats should "
                    f"early-return; got stats={fresh.stats!r}"
                )

        # ── 8. Assertion 5 — sibling unit's CRM has no leaked entries.
        async with Sf() as s:
            sibling_entries = await _read_data_entries(
                s, carbon_report_module_id=sibling_crm.id
            )
        assert sibling_entries == [], (
            f"sibling unit's CRM (module_type={spec.module_type.name}) "
            f"received DataEntries — chain leaked across units. "
            f"got {len(sibling_entries)} rows."
        )

    finally:
        await engine.dispose()
