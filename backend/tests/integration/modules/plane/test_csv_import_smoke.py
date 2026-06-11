"""Integration smoke for the plane ``_process_batch`` carrier flow.

Exercises the second half of the CSV ingestion pipeline end-to-end
against a real DB session: a batch of plane ``DataEntry`` rows
(constructed by hand, mirroring what
``BaseCSVProvider._process_row`` produces — i.e. ``kg_co2eq`` already
stripped from ``data``) goes through the same ``_process_batch``
routine the production CSV upload uses, backed by the real
``DataEntryService`` and ``DataEntryEmissionService``.

Asserts the two invariants from the PR's manual test plan:

1. After the import, ``data_entries.data`` rows must NOT contain a
   ``kg_co2eq`` key — the override is carried out-of-band.
2. ``data_entry_emissions.kg_co2eq`` must carry the imported override
   value, and the row must have ``primary_factor_id=None`` (override
   bypasses the formula path).

**Coverage seam — what this test does NOT exercise:**

- The ``CSV row → _process_row → 4-tuple`` half of the pipeline. That's
  unit-tested in ``tests/unit/services/data_ingestion/test_base_csv_provider.py``
  (``test_process_row_consumes_dumb_csv_fixture_for_plane`` and
  siblings). The two tests together sandwich the full CSV import path,
  but no single test reads the fixture file and runs it through both
  halves end-to-end.
- The ``user`` / audit-versioning branch of ``DataEntryService.bulk_create``
  (we pass ``user=None`` to keep the test focused on persistence). If
  a future change to that branch accidentally mutated ``data_entry.data``,
  this test would not catch it.
"""

import csv
from pathlib import Path
from typing import Any

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import EmissionType
from app.models.data_ingestion import EntityType
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.base_csv_provider import BaseCSVProvider


class _MinimalPlaneCSVProvider(BaseCSVProvider):
    """Just enough of a CSV provider to drive ``_process_batch`` against
    a real DB. Skips the file-store / job-row / setup machinery."""

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_UNIT_SPECIFIC

    async def _setup_handlers_and_factors(self):
        return {}

    def _extract_kind_subkind_values(self, filtered_row, handlers):
        return (None, None)

    async def _resolve_handler_and_validate(
        self, filtered_row, factor, stats, row_idx, max_row_errors, setup_result
    ):
        return (None, None, None)


def _make_provider(data_session: AsyncSession) -> _MinimalPlaneCSVProvider:
    """Construct the minimal provider with a real DB session."""
    config: dict[str, Any] = {"file_path": "tmp/test.csv"}
    provider = _MinimalPlaneCSVProvider(
        config,
        data_session=data_session,
        user=None,
    )
    # `_process_batch` looks up the report year from this cache before
    # falling back to a DB query — pre-populating skips the lookup.
    provider._year_cache = {}
    return provider


@pytest.mark.asyncio
async def test_process_batch_carrier_keeps_kg_co2eq_out_of_data_entry(
    db_session: AsyncSession,
):
    """End-to-end carrier verification: feed the real services a 3-entry batch
    matching the plane fixture (GVA→ZRH/CDG→JFK/GVA→LHR) and verify that
    ``DataEntry.data`` stays clean (no kg_co2eq leak) and the
    ``__kg_co2eq_override__`` carrier is persisted for the async recalc chain.
    """
    # ---------- arrange: factor + module --------------------------------
    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status=ModuleStatus.NOT_STARTED,
    )
    db_session.add(module)
    await db_session.flush()

    factor = Factor(
        emission_type_id=EmissionType.professional_travel__plane.value,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        classification={"category": "very_short_haul", "year": 2025},
        values={
            "ef_kg_co2eq_per_km": 0.174,
            "rfi_adjustment": 2.7,
        },
        year=2025,
    )
    db_session.add(factor)
    await db_session.commit()

    provider = _make_provider(db_session)
    provider._year_cache = {module.id: 2025}

    # ---------- arrange: rows derived from the actual CSV fixture -------
    # The same fixture file the unit test consumes via csv.DictReader.
    # Mirroring what BaseCSVProvider._process_row produces: kg_co2eq is
    # extracted out-of-band into the parallel overrides list and the
    # remaining columns become DataEntry.data with primary_factor_id=None.
    fixture_path = (
        Path(__file__).parent.parent.parent
        / "data_ingestion"
        / "fixtures"
        / "regression_kg_co2eq_plane.csv"
    )
    assert fixture_path.exists(), f"missing fixture: {fixture_path}"

    batch: list[DataEntry] = []
    overrides: list[float | None] = []
    expected_originals: list[dict] = []
    with open(fixture_path, encoding="utf-8") as f:
        for raw_row in csv.DictReader(f):
            kg_str = raw_row.pop("kg_co2eq")  # carry out-of-band, never persist
            row_data = {
                "origin_iata": raw_row["origin_iata"],
                "destination_iata": raw_row["destination_iata"],
                "cabin_class": raw_row["cabin_class"],
                "user_institutional_id": raw_row["user_institutional_id"],
                "number_of_trips": int(raw_row["number_of_trips"]),
                "primary_factor_id": None,
            }
            batch.append(
                DataEntry(
                    carbon_report_module_id=module.id,
                    data_entry_type_id=DataEntryTypeEnum.plane,
                    data=dict(row_data),
                )
            )
            overrides.append(float(kg_str))
            expected_originals.append(row_data)

    assert len(batch) >= 2, (
        "fixture should provide enough rows to exercise multi-entry routing"
    )

    # ---------- act: run the real carrier through _process_batch --------
    data_entry_service = DataEntryService(db_session)
    emission_service = DataEntryEmissionService(db_session)
    await provider._process_batch(
        batch,
        data_entry_service,
        emission_service,
        None,  # user — bypasses audit/version logic
        overrides,
    )

    # ---------- assert (1): persisted DataEntry.data is clean -----------
    # Note: DataEntryRepository.bulk_create constructs *new* ORM
    # instances internally (model_validate), so the originals in `batch`
    # never get their .id populated. Re-read from the DB.
    persisted_entries = list(
        (
            await db_session.execute(
                select(DataEntry)
                .where(DataEntry.carbon_report_module_id == module.id)
                .order_by(DataEntry.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(persisted_entries) == len(batch), (
        f"expected {len(batch)} persisted plane rows, got {len(persisted_entries)}"
    )

    # Key by (origin, destination) — origin alone isn't unique in the
    # fixture (GVA appears twice, paired with ZRH and LHR).
    persisted_by_route = {
        (e.data["origin_iata"], e.data["destination_iata"]): e
        for e in persisted_entries
    }
    for original in expected_originals:
        route = (original["origin_iata"], original["destination_iata"])
        e = persisted_by_route[route]
        assert e.data == original, (
            f"DataEntry.data was mutated by the import.\n"
            f"  expected: {original!r}\n"
            f"  actual:   {e.data!r}"
        )
        assert "kg_co2eq" not in e.data, (
            f"kg_co2eq leaked into DataEntry.data: {e.data!r}"
        )

    # ---------- assert (2): __kg_co2eq_override__ carrier is persisted -----
    # The async recalc chain reads this key from DataEntry.data as a fallback
    # in prepare_create — it must survive bulk_create.
    override_by_route = {
        (original["origin_iata"], original["destination_iata"]): ov
        for original, ov in zip(expected_originals, overrides, strict=True)
    }
    for entry in persisted_entries:
        route = (entry.data["origin_iata"], entry.data["destination_iata"])
        expected_kg = override_by_route[route]
        assert entry.data.get("__kg_co2eq_override__") == pytest.approx(expected_kg), (
            f"missing __kg_co2eq_override__ for route {route}: {entry.data!r}"
        )
