"""Plan 310 test-coverage — Unit 4 (professional_travel: plane + train).

Covers the only data-ingestion module with all three of:

* an ``EXTERNAL_INTEGRATION`` source path (Tableau via
  ``ProfessionalTravelApiProvider``) that carries a per-row
  ``kg_co2eq`` override,
* location-based ref-data lookups (IATA airports for plane,
  station name for train) gated by ``LocationService``, and
* a strict 1-1 invariant between ``data_entries`` and
  ``data_entry_emissions`` for the module (one entry → exactly
  one emission, no rollups).

Asserts, per submodule (plane, train):

1. ``BaseCSVProvider`` (``ModulePerYearCSVProvider``) persists CSV
   rows with the right ``DataEntrySourceEnum`` value.
2. ``ProfessionalTravelApiProvider._load_data`` persists rows with
   ``source = EXTERNAL_INTEGRATION`` and writes the Tableau
   ``OUT_CO2_CORRECTED`` / ``kg_co2eq`` value into
   ``DataEntry.data[__kg_co2eq_override__]``.  Pins the V2 fix —
   ``kg_co2eq=0`` and ``kg_co2eq=0.0`` SURVIVE the override channel
   (``is not None`` rather than truthy check).
3. The 1-1 invariant: after every successful ingest,
   ``count(data_entry_emissions for module) == count(data_entries
   for module)``.
4. Discovery — when ``LocationService.get_location_by_iata`` /
   ``get_location_by_name`` returns ``None``, the data entry
   persists but no emission is computed (``pre_compute`` returns
   ``{}`` which short-circuits the FactorQuery).  Document the
   actual behaviour rather than assert 1-1 (entry-with-no-emission
   is the legitimate semantics).
5. Reupload: re-uploading ``travel_planes_smoke.csv`` replaces the
   prior CSV-sourced rows and preserves the 1-1 invariant.

Plus extends ``test_kg_co2eq_override_async_path_pg.py`` with two
travel-shaped tests asserting that ``__kg_co2eq_override__=0`` and
``=0.0`` survive the runner-driven async recalc path.

Requires Docker — see ``conftest.py``'s ``postgres_container``
fixture.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import (
    CarbonReport,
    CarbonReportModule,
    CarbonReportType,
)
from app.models.data_entry import (
    DataEntry,
    DataEntrySourceEnum,
    DataEntryTypeEnum,
)
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.models.location import Location, TransportModeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import (
    KG_CO2EQ_OVERRIDE_KEY,
    DataEntryEmissionService,
)
from app.services.data_ingestion.api_providers.professional_travel_api_provider import (  # noqa: E501
    ProfessionalTravelApiProvider,
)
from app.services.data_ingestion.csv_providers import ModulePerYearCSVProvider

from .conftest import csv_fixture_path, dispatch_csv_and_wait

# Year used by all tests in this module — kept distinct from the years
# the rest of the test file uses to avoid YearConfiguration collisions
# under a shared session.
YEAR = 2025

# Single canonical unit institutional id matching all trimmed CSV rows.
UNIT_INST_ID = "TC-TRAVEL-1"


# ── Helpers ────────────────────────────────────────────────────────────


async def _seed_year_unit_and_module(
    session: AsyncSession,
    *,
    year: int = YEAR,
    institutional_id: str = UNIT_INST_ID,
) -> tuple[int, int, int]:
    """Lay down the (YearConfiguration, Unit, CarbonProject, CarbonReport,
    CarbonReportModule[professional_travel]) tree the CSV ingest needs
    to resolve ``unit_institutional_id`` → ``carbon_report_module_id``.

    Returns ``(unit_id, carbon_report_id, module_id)``.

    Hand-rolled rather than ``seeded_year_with_units`` because the CSV
    rows reference a fixed ``unit_institutional_id`` — we cannot use the
    foundation helper's ``SEED-{suffix}-{i}`` shape.
    """
    # YearConfiguration may already exist if multiple tests share a session.
    existing = await session.get(YearConfiguration, (year, UserProvider.DEFAULT))
    if existing is None:
        session.add(
            YearConfiguration(year=year, provider=UserProvider.DEFAULT, is_started=True)
        )
        await session.flush()

    unit = Unit(
        provider=UserProvider.DEFAULT,
        institutional_code=f"CODE-{institutional_id}",
        institutional_id=institutional_id,
        name=f"Travel Test Unit {institutional_id}",
        level=2,
        is_active=True,
    )
    session.add(unit)
    await session.flush()
    assert unit.id is not None

    project = CarbonProject(
        unit_id=unit.id,
        carbon_report_type=CarbonReportType.CALCULATOR,
    )
    session.add(project)
    await session.flush()

    report = CarbonReport(
        year=year,
        unit_id=unit.id,
        carbon_project_id=project.id,
    )
    session.add(report)
    await session.flush()
    assert report.id is not None

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=int(ModuleTypeEnum.professional_travel),
    )
    session.add(module)
    await session.flush()
    assert module.id is not None

    await session.commit()
    return unit.id, report.id, module.id


async def _seed_plane_locations(session: AsyncSession) -> None:
    """Two airports for the trimmed plane fixture (GVA / CDG)."""
    session.add_all(
        [
            Location(
                transport_mode=TransportModeEnum.plane,
                name="Geneva",
                iata_code="GVA",
                latitude=46.2381,
                longitude=6.1090,
                country_code="CH",
                natural_key=Location.compute_natural_key(
                    transport_mode=TransportModeEnum.plane,
                    iata_code="GVA",
                ),
            ),
            Location(
                transport_mode=TransportModeEnum.plane,
                name="Paris CDG",
                iata_code="CDG",
                latitude=49.0097,
                longitude=2.5479,
                country_code="FR",
                natural_key=Location.compute_natural_key(
                    transport_mode=TransportModeEnum.plane,
                    iata_code="CDG",
                ),
            ),
        ]
    )
    await session.commit()


async def _seed_train_locations(session: AsyncSession) -> None:
    """Two stations for the trimmed train fixture (Geneva / Lausanne)."""
    session.add_all(
        [
            Location(
                transport_mode=TransportModeEnum.train,
                name="Geneva",
                latitude=46.2104,
                longitude=6.1428,
                country_code="CH",
                natural_key=Location.compute_natural_key(
                    transport_mode=TransportModeEnum.train,
                    name="Geneva",
                    latitude=46.2104,
                    longitude=6.1428,
                    country_code="CH",
                ),
            ),
            Location(
                transport_mode=TransportModeEnum.train,
                name="Lausanne",
                latitude=46.5167,
                longitude=6.6322,
                country_code="CH",
                natural_key=Location.compute_natural_key(
                    transport_mode=TransportModeEnum.train,
                    name="Lausanne",
                    latitude=46.5167,
                    longitude=6.6322,
                    country_code="CH",
                ),
            ),
        ]
    )
    await session.commit()


async def _seed_plane_factor(session: AsyncSession) -> int:
    factor = Factor(
        emission_type_id=EmissionType.professional_travel__plane.value,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        # The trimmed CSV's GVA→CDG distance lands in the very_short_haul
        # bucket (haul category derived in pre_compute).
        classification={"category": "very_short_haul", "cabin_class": "economy"},
        values={
            "ef_kg_co2eq_per_km": 0.1,
            "min_distance": 0,
            "max_distance": 800,
        },
        year=YEAR,
    )
    session.add(factor)
    await session.commit()
    assert factor.id is not None
    return factor.id


async def _seed_train_factor(session: AsyncSession) -> int:
    factor = Factor(
        emission_type_id=EmissionType.professional_travel__train.value,
        data_entry_type_id=DataEntryTypeEnum.train.value,
        classification={"country_code": "CH"},
        values={"ef_kg_co2eq_per_km": 0.05},
        year=YEAR,
    )
    session.add(factor)
    await session.commit()
    assert factor.id is not None
    return factor.id


def _stage_csv_under_files_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fixture_path: Path,
) -> str:
    """Copy a trimmed fixture CSV into ``<tmp_path>/tmp/`` and patch the
    settings so ``LocalFilesStore`` resolves relative paths against
    ``tmp_path``.

    Returns the relative path (e.g. ``"tmp/travel_planes_smoke.csv"``)
    that the CSV provider's ``_validate_file_path`` will accept.

    The CSV provider rejects absolute paths and demands one of
    ``tmp/``, ``uploads/``, ``temporary/`` prefixes.  Pattern mirrors
    ``test_plan_310b_factor_reupload_endpoint_pg.py``: the test fixture
    ships under ``backend/tests/fixtures/csv/`` (committed, CI-safe),
    and we copy it into the per-test ``tmp_path`` so the
    ``LocalFilesStore`` reads it at the relative path the validator
    expects.  Disabling encryption (``FILES_ENCRYPTION_KEY=""``) keeps
    the plaintext CSV readable.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "FILES_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "FILES_ENCRYPTION_KEY", "")
    monkeypatch.setattr(settings, "FILES_ENCRYPTION_SALT", "")

    target_dir = tmp_path / "tmp"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / fixture_path.name
    shutil.copyfile(fixture_path, target)
    return f"tmp/{fixture_path.name}"


async def _count_entries_and_emissions_for_module(
    session: AsyncSession,
    *,
    module_id: int,
) -> tuple[int, int]:
    """Return ``(n_entries, n_emissions)`` for the given carbon-report
    module.  Used to pin the 1-1 invariant: travel is the only module
    where ``n_emissions == n_entries`` (no rollups, single emission per
    entry from ``resolve_computations`` returning a single
    ``EmissionComputation``).
    """
    n_entries = (
        await session.execute(
            select(func.count())
            .select_from(DataEntry)
            .where(col(DataEntry.carbon_report_module_id) == module_id)
        )
    ).scalar_one()

    # Count emissions whose data_entry's CRM matches the module.
    n_emissions = (
        await session.execute(
            select(func.count())
            .select_from(DataEntryEmission)
            .join(DataEntry, col(DataEntryEmission.data_entry_id) == col(DataEntry.id))
            .where(col(DataEntry.carbon_report_module_id) == module_id)
        )
    ).scalar_one()

    return int(n_entries), int(n_emissions)


# ── 1. CSV ingest, plane ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plane_csv_persists_csv_source_and_preserves_one_to_one(
    pg_dsn, monkeypatch, tmp_path
) -> None:
    """``ModulePerYearCSVProvider`` ingests the plane smoke CSV: every
    row persists with ``source = CSV_MODULE_PER_YEAR``, every entry
    yields exactly one emission row (1-1 invariant), and emissions are
    non-zero (proving the location lookup + factor match worked).
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, _, module_id = await _seed_year_unit_and_module(s)
        await _seed_plane_locations(s)
        await _seed_plane_factor(s)

    relative_path = _stage_csv_under_files_store(
        monkeypatch, tmp_path, csv_fixture_path("travel_planes", "data")
    )

    parent, _ = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=relative_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.professional_travel),
        data_entry_type_id=int(DataEntryTypeEnum.plane),
        year=YEAR,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    assert parent.state == IngestionState.FINISHED, (
        f"csv_ingest parent did not finish: state={parent.state} "
        f"status={parent.status_message!r}"
    )
    assert parent.result == IngestionResult.SUCCESS, (
        f"csv_ingest parent reported {parent.result}: {parent.status_message!r}"
    )

    async with Sf() as s:
        rows = (
            (
                await s.execute(
                    select(DataEntry).where(
                        col(DataEntry.carbon_report_module_id) == module_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2, f"trimmed plane CSV has 2 rows; persisted {len(rows)}"
        for r in rows:
            assert r.source == DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value, (
                f"plane CSV row source={r.source}, "
                f"expected {DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value}"
            )
            assert r.data_entry_type_id == DataEntryTypeEnum.plane.value

        n_entries, n_emissions = await _count_entries_and_emissions_for_module(
            s, module_id=module_id
        )
        assert n_entries == n_emissions, (
            f"travel/plane 1-1 invariant broken: "
            f"entries={n_entries} emissions={n_emissions}"
        )
        assert n_emissions > 0, (
            "expected ≥1 emission — locations + factor were seeded, so the "
            "plane CSV path should have produced emissions"
        )

    await engine.dispose()


# ── 2. CSV ingest, train ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_train_csv_persists_csv_source_and_preserves_one_to_one(
    pg_dsn, monkeypatch, tmp_path
) -> None:
    """Train sibling of the plane CSV smoke: same contracts (CSV source
    enum, 1-1 invariant, non-zero emissions) against the train fixture
    + station-name LocationService lookup.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, _, module_id = await _seed_year_unit_and_module(s)
        await _seed_train_locations(s)
        await _seed_train_factor(s)

    relative_path = _stage_csv_under_files_store(
        monkeypatch, tmp_path, csv_fixture_path("travel_trains", "data")
    )

    parent, _ = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=relative_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.professional_travel),
        data_entry_type_id=int(DataEntryTypeEnum.train),
        year=YEAR,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    assert parent.state == IngestionState.FINISHED, (
        f"train csv_ingest parent did not finish: state={parent.state} "
        f"status={parent.status_message!r}"
    )
    assert parent.result == IngestionResult.SUCCESS, (
        f"train csv_ingest parent reported {parent.result}: {parent.status_message!r}"
    )

    async with Sf() as s:
        rows = (
            (
                await s.execute(
                    select(DataEntry).where(
                        col(DataEntry.carbon_report_module_id) == module_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2, f"trimmed train CSV has 2 rows; persisted {len(rows)}"
        for r in rows:
            assert r.source == DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value
            assert r.data_entry_type_id == DataEntryTypeEnum.train.value

        n_entries, n_emissions = await _count_entries_and_emissions_for_module(
            s, module_id=module_id
        )
        assert n_entries == n_emissions, (
            f"travel/train 1-1 invariant broken: "
            f"entries={n_entries} emissions={n_emissions}"
        )
        assert n_emissions > 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_train_csv_resolves_station_by_required_country_code(
    pg_dsn, monkeypatch, tmp_path
) -> None:
    """Regression for issue #1183: the train CSV's required
    ``origin_country_code`` / ``destination_country_code`` columns scope
    station resolution to one country.

    Setup pins the cross-country collision case from the issue body:
    two stations share the same name (``Berne``) in different
    countries (CH vs DE). A single CSV row with
    ``destination_country_code=DE`` must resolve to the German station,
    not the Swiss one. (Missing country_code is rejected — covered by the
    unit test ``test_train_enrich_csv_row``.)
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    de_natural_key = Location.compute_natural_key(
        transport_mode=TransportModeEnum.train,
        name="Berne",
        latitude=53.1667,
        longitude=8.5,
        country_code="DE",
    )

    async with Sf() as s:
        _, _, module_id = await _seed_year_unit_and_module(s)
        # Origin: Geneva (CH) — same as the smoke fixture.
        s.add(
            Location(
                transport_mode=TransportModeEnum.train,
                name="Geneva",
                latitude=46.2104,
                longitude=6.1428,
                country_code="CH",
                natural_key=Location.compute_natural_key(
                    transport_mode=TransportModeEnum.train,
                    name="Geneva",
                    latitude=46.2104,
                    longitude=6.1428,
                    country_code="CH",
                ),
            )
        )
        # Collision pair: Berne exists in both CH and DE.
        s.add(
            Location(
                transport_mode=TransportModeEnum.train,
                name="Berne",
                latitude=46.948,
                longitude=7.4474,
                country_code="CH",
                natural_key=Location.compute_natural_key(
                    transport_mode=TransportModeEnum.train,
                    name="Berne",
                    latitude=46.948,
                    longitude=7.4474,
                    country_code="CH",
                ),
            )
        )
        s.add(
            Location(
                transport_mode=TransportModeEnum.train,
                name="Berne",
                latitude=53.1667,
                longitude=8.5,
                country_code="DE",
                natural_key=de_natural_key,
            )
        )
        await s.commit()
        await _seed_train_factor(s)

    csv_path = tmp_path / "train_country_code_override.csv"
    csv_path.write_text(
        "unit_institutional_id,origin_name,origin_country_code,"
        "destination_name,destination_country_code,user_institutional_id,"
        "departure_date,number_of_trips,cabin_class,note,kg_co2eq\n"
        f"{UNIT_INST_ID},Geneva,CH,Berne,DE,U-DE,2025-04-01,1,second,,\n"
    )
    relative_path = _stage_csv_under_files_store(monkeypatch, tmp_path, csv_path)

    parent, _ = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=relative_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.professional_travel),
        data_entry_type_id=int(DataEntryTypeEnum.train),
        year=YEAR,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    assert parent.state == IngestionState.FINISHED, (
        f"country_code-override CSV did not finish: state={parent.state} "
        f"status={parent.status_message!r}"
    )
    assert parent.result == IngestionResult.SUCCESS, (
        f"country_code-override CSV reported {parent.result}: {parent.status_message!r}"
    )

    async with Sf() as s:
        rows = (
            (
                await s.execute(
                    select(DataEntry).where(
                        col(DataEntry.carbon_report_module_id) == module_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1, f"expected single override row; persisted {len(rows)}"
        persisted = rows[0]
        assert persisted.data.get("destination_natural_key") == de_natural_key, (
            "destination_country_code=DE must resolve to the German Berne "
            "station, not the Swiss default — got "
            f"{persisted.data.get('destination_natural_key')!r}"
        )

    await engine.dispose()


# ── 3. CSV reupload ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plane_csv_reupload_replaces_old_rows_and_preserves_one_to_one(
    pg_dsn, monkeypatch, tmp_path
) -> None:
    """Re-uploading the same plane CSV must replace the prior
    ``CSV_MODULE_PER_YEAR`` rows (the bulk path's
    ``_delete_existing_csv_module_per_year_entries`` step) rather than
    accumulate, and the 1-1 invariant must still hold post-reupload.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, _, module_id = await _seed_year_unit_and_module(s)
        await _seed_plane_locations(s)
        await _seed_plane_factor(s)

    relative_path = _stage_csv_under_files_store(
        monkeypatch, tmp_path, csv_fixture_path("travel_planes", "data")
    )

    # First upload.
    parent_1, _ = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=relative_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.professional_travel),
        data_entry_type_id=int(DataEntryTypeEnum.plane),
        year=YEAR,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    assert parent_1.result == IngestionResult.SUCCESS

    async with Sf() as s:
        first_ids = {
            row.id
            for row in (
                (
                    await s.execute(
                        select(DataEntry).where(
                            col(DataEntry.carbon_report_module_id) == module_id
                        )
                    )
                )
                .scalars()
                .all()
            )
        }
        assert len(first_ids) == 2

    # The partial unique index ``ix_data_ingestion_jobs_is_current_unique``
    # only allows one ``is_current=True`` job per (module_type, det,
    # target, method, year).  In production ``mark_as_current`` flips
    # the prior current row to ``False`` *before* the new INSERT; the
    # foundation helper inserts the parent with ``is_current=True``
    # directly, so the second dispatch races the index.  Manually
    # demote the prior parent here — the contract under test is the
    # CSV-row replacement, not the job-row uniqueness machinery (that
    # has its own coverage in ``test_pod_safety_310a_pg.py``).
    async with Sf() as s:
        prior = await s.get(DataIngestionJob, parent_1.id)
        if prior is not None:
            prior.is_current = False
            s.add(prior)
            await s.commit()

    # Second upload — same CSV.  Some providers move the source file
    # post-process, so re-stage to keep the relative path resolvable.
    relative_path = _stage_csv_under_files_store(
        monkeypatch, tmp_path, csv_fixture_path("travel_planes", "data")
    )
    parent_2, _ = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=relative_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.professional_travel),
        data_entry_type_id=int(DataEntryTypeEnum.plane),
        year=YEAR,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    assert parent_2.result == IngestionResult.SUCCESS, (
        f"reupload parent reported {parent_2.result}: {parent_2.status_message!r}"
    )

    async with Sf() as s:
        rows = (
            (
                await s.execute(
                    select(DataEntry).where(
                        col(DataEntry.carbon_report_module_id) == module_id
                    )
                )
            )
            .scalars()
            .all()
        )
        # The prior CSV-sourced entries were deleted before reinsertion —
        # otherwise the count would be 4.
        assert len(rows) == 2, (
            f"reupload should replace prior rows, not accumulate; got {len(rows)}"
        )
        # All new rows have ids strictly greater than every original id —
        # proves the prior set was deleted, not updated in place.
        new_ids = {r.id for r in rows}
        assert new_ids.isdisjoint(first_ids), (
            f"reupload kept old ids: new={new_ids}, first={first_ids}"
        )

        # 1-1 still holds post-reupload.
        n_entries, n_emissions = await _count_entries_and_emissions_for_module(
            s, module_id=module_id
        )
        assert n_entries == n_emissions, (
            f"reupload broke 1-1 invariant: entries={n_entries} emissions={n_emissions}"
        )
        assert n_emissions > 0

    await engine.dispose()


# ── 4. Discovery — unknown IATA / unknown station name ─────────────────


@pytest.mark.asyncio
async def test_plane_unknown_iata_persists_entry_without_emission(
    pg_dsn, monkeypatch, tmp_path
) -> None:
    """Discovery: an unknown destination IATA causes
    ``LocationService.get_location_by_iata`` to return ``None``,
    ``pre_compute`` returns ``{}``, and ``resolve_computations`` is
    never asked for an EmissionComputation against an empty haul
    category.

    Observed behaviour as of 310-D: the data entry persists with a
    ``CSV_MODULE_PER_YEAR`` source but no emission row is computed.
    The 1-1 invariant is intentionally NOT asserted here — the contract
    we pin instead is "missing location → entry without emission",
    which is the legitimate semantics for unresolvable trips and the
    motivation for the discovery test in the spec.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, _, module_id = await _seed_year_unit_and_module(s)
        # Only seed origin (GVA) — destination XXX must miss.
        s.add(
            Location(
                transport_mode=TransportModeEnum.plane,
                name="Geneva",
                iata_code="GVA",
                latitude=46.2381,
                longitude=6.1090,
                country_code="CH",
                natural_key=Location.compute_natural_key(
                    transport_mode=TransportModeEnum.plane,
                    iata_code="GVA",
                ),
            )
        )
        await s.commit()
        await _seed_plane_factor(s)

    relative_path = _stage_csv_under_files_store(
        monkeypatch, tmp_path, csv_fixture_path("travel_planes", "unknown_iata")
    )

    parent, _ = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=relative_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.professional_travel),
        data_entry_type_id=int(DataEntryTypeEnum.plane),
        year=YEAR,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    # SUCCESS or WARNING are both acceptable here — the row count is the
    # contract.  The chain itself must finish (no crash).
    assert parent.state == IngestionState.FINISHED

    async with Sf() as s:
        rows = (
            (
                await s.execute(
                    select(DataEntry).where(
                        col(DataEntry.carbon_report_module_id) == module_id
                    )
                )
            )
            .scalars()
            .all()
        )
        # Document the observed behaviour: the entry IS persisted by the
        # CSV provider even though pre_compute will return {} for it.
        assert len(rows) == 1, (
            f"unknown IATA should still persist the data entry; got {len(rows)} rows"
        )

        n_entries, n_emissions = await _count_entries_and_emissions_for_module(
            s, module_id=module_id
        )
        # Pin the asymmetry: entry persists but no emission was
        # computed (pre_compute returned {}, FactorQuery never fired).
        assert n_entries == 1
        assert n_emissions == 0, (
            f"unknown-IATA entry should produce 0 emissions; got {n_emissions}"
        )

    await engine.dispose()


@pytest.mark.asyncio
async def test_train_unknown_station_persists_entry_without_emission(
    pg_dsn, monkeypatch, tmp_path
) -> None:
    """Train mirror of the unknown-IATA discovery test: unknown station
    name → no Location → ``pre_compute`` returns ``{}`` → entry without
    emission.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, _, module_id = await _seed_year_unit_and_module(s)
        # Only seed origin (Geneva) — destination "Atlantis" must miss.
        s.add(
            Location(
                transport_mode=TransportModeEnum.train,
                name="Geneva",
                latitude=46.2104,
                longitude=6.1428,
                country_code="CH",
                natural_key=Location.compute_natural_key(
                    transport_mode=TransportModeEnum.train,
                    name="Geneva",
                    latitude=46.2104,
                    longitude=6.1428,
                    country_code="CH",
                ),
            )
        )
        await s.commit()
        await _seed_train_factor(s)

    relative_path = _stage_csv_under_files_store(
        monkeypatch, tmp_path, csv_fixture_path("travel_trains", "unknown_station")
    )

    parent, _ = await dispatch_csv_and_wait(
        session_factory=Sf,
        file_path=relative_path,
        target_type=TargetType.DATA_ENTRIES,
        module_type_id=int(ModuleTypeEnum.professional_travel),
        data_entry_type_id=int(DataEntryTypeEnum.train),
        year=YEAR,
        ingestion_method=IngestionMethod.csv,
        provider_class=ModulePerYearCSVProvider,
    )
    assert parent.state == IngestionState.FINISHED

    async with Sf() as s:
        n_entries, n_emissions = await _count_entries_and_emissions_for_module(
            s, module_id=module_id
        )
        assert n_entries == 1, (
            f"unknown-station entry should still persist; got {n_entries}"
        )
        assert n_emissions == 0, (
            f"unknown-station entry should yield 0 emissions; got {n_emissions}"
        )

    await engine.dispose()


# ── 5. EXTERNAL_INTEGRATION via ProfessionalTravelApiProvider ──────────


def _make_api_provider(
    *,
    data_session: AsyncSession,
    job_session: AsyncSession,
    user: Any,
) -> ProfessionalTravelApiProvider:
    """Build a ``ProfessionalTravelApiProvider`` against the test
    sessions.

    Side-steps the Tableau settings dance — we never call ``ingest()``,
    only ``_load_data()``, so the JWT/HTTP attributes don't need to be
    real.  ``module_type_id`` IS required because ``_load_data`` calls
    ``DataEntryService.bulk_create`` which doesn't read it, but the
    provider's transform layer would.
    """
    config = {
        "module_type_id": int(ModuleTypeEnum.professional_travel),
        "year": YEAR,
    }
    # Stub the Tableau settings only during __init__.  ``_load_data``
    # later calls ``get_settings().BULK_PATH_PURE_ASYNC`` against the
    # real settings — that's intentional, since the production default
    # (True) IS the path under test.  If the default ever flips this
    # test will silently change branches; the assertions still pin the
    # source enum and override carrier on whichever path runs.
    with patch(
        "app.services.data_ingestion.api_providers.professional_travel_api_provider"
        ".get_settings"
    ) as mock_settings:
        mock_settings.return_value = MagicMock(
            TABLEAU_SERVER_URL="https://stub",
            TABLEAU_SITE_CONTENT_URL="stub",
            TABLEAU_DS_FLIGHTS_LUID="stub",
            TABLEAU_CONNECTED_APP_CLIENT_ID="stub",
            TABLEAU_CONNECTED_APP_SECRET_ID="stub",
            TABLEAU_CONNECTED_APP_SECRET_VALUE="stub",
            TABLEAU_REQUEST_TIMEOUT_SECONDS=10,
            TABLEAU_VERIFY_SSL="false",
            TABLEAU_REST_MIN_API_VERSION="3.20",
            TABLEAU_MAX_FIELDS=200,
            TABLEAU_USERNAME="stub",
            BULK_PATH_PURE_ASYNC=True,
        )
        provider = ProfessionalTravelApiProvider(
            config=config,
            user=user,
            job_session=job_session,
            data_session=data_session,
        )
    # Job id is set by ``set_job_id`` in production; stash a sentinel so
    # ``bulk_create`` has something for ``created_by_id`` / ``job_id``.
    provider.job_id = 1
    return provider


@pytest.mark.asyncio
async def test_api_provider_load_data_persists_external_integration_with_zero_overrides(  # noqa: E501
    pg_dsn,
) -> None:
    """``ProfessionalTravelApiProvider._load_data`` must persist:

    * ``DataEntry.source = EXTERNAL_INTEGRATION`` (5)
    * The override carrier ``__kg_co2eq_override__`` for every record
      with a non-``None`` ``kg_co2eq`` — INCLUDING ``0`` and ``0.0``.

    This pins the V2 ``is not None`` fix at the source: a falsy zero
    must NOT collapse to ``OUT_CO2_CORRECTED`` fallback (the V1 ``or``
    bug — walking legs and fully-electric trips on green grids would
    silently inherit the fallback).
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, _, module_id = await _seed_year_unit_and_module(s)

    # Three records exercising the V2 `is not None` boundary:
    #   * row 0: explicit kg_co2eq=0     (must be preserved as 0.0)
    #   * row 1: explicit kg_co2eq=0.0   (must be preserved as 0.0)
    #   * row 2: kg_co2eq=None, OUT_CO2_CORRECTED=5.0
    #            (fallback path must populate carrier with 5.0)
    records: list[dict[str, Any]] = [
        {
            "carbon_report_module_id": module_id,
            "user_institutional_id": "U-API-0",
            "origin_iata": "GVA",
            "destination_iata": "CDG",
            "kg_co2eq": 0,  # int zero
            "OUT_CO2_CORRECTED": 999.0,  # must NOT win
            "number_of_trips": 1,
            "cabin_class": "economy",
        },
        {
            "carbon_report_module_id": module_id,
            "user_institutional_id": "U-API-1",
            "origin_iata": "GVA",
            "destination_iata": "CDG",
            "kg_co2eq": 0.0,  # float zero
            "OUT_CO2_CORRECTED": 999.0,
            "number_of_trips": 1,
            "cabin_class": "economy",
        },
        {
            "carbon_report_module_id": module_id,
            "user_institutional_id": "U-API-2",
            "origin_iata": "GVA",
            "destination_iata": "CDG",
            "kg_co2eq": None,  # missing → fallback applies
            "OUT_CO2_CORRECTED": 5.0,
            "number_of_trips": 1,
            "cabin_class": "economy",
        },
    ]

    async with Sf() as data_session, Sf() as job_session:
        provider = _make_api_provider(
            data_session=data_session, job_session=job_session, user=None
        )
        result = await provider._load_data(records)
        await data_session.commit()
    assert result["inserted"] == 3, f"expected 3 entries, got {result}"

    async with Sf() as s:
        rows = (
            (
                await s.execute(
                    select(DataEntry)
                    .where(col(DataEntry.carbon_report_module_id) == module_id)
                    .order_by(col(DataEntry.id))
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 3
        for r in rows:
            assert r.source == DataEntrySourceEnum.EXTERNAL_INTEGRATION.value, (
                f"API row source={r.source}, expected "
                f"{DataEntrySourceEnum.EXTERNAL_INTEGRATION.value}"
            )
            assert r.data_entry_type_id == DataEntryTypeEnum.plane.value, (
                f"API provider hard-codes plane data_entry_type — got "
                f"{r.data_entry_type_id}"
            )
            # The reserved override carrier was set on every record.
            assert KG_CO2EQ_OVERRIDE_KEY in r.data, (
                f"override carrier missing from record: {r.data!r}"
            )
            # And the raw `kg_co2eq` key was stripped from the persisted
            # payload (B-H1 sanitisation — guards against the override
            # leaking back into formula recomputes).
            assert "kg_co2eq" not in r.data, (
                f"raw kg_co2eq leaked into persisted data: {r.data!r}"
            )

        overrides_by_user = {
            r.data["user_institutional_id"]: r.data[KG_CO2EQ_OVERRIDE_KEY] for r in rows
        }
        # V2 fix — int 0 + float 0.0 both survive as 0.0 (NOT replaced
        # by the 999.0 OUT_CO2_CORRECTED fallback).
        assert overrides_by_user["U-API-0"] == 0.0, overrides_by_user
        assert overrides_by_user["U-API-1"] == 0.0, overrides_by_user
        # None falls through to OUT_CO2_CORRECTED.
        assert overrides_by_user["U-API-2"] == 5.0, overrides_by_user

    await engine.dispose()


# ── 6. End-to-end async-recalc preservation of zero override ───────────


@pytest.mark.asyncio
async def test_kg_co2eq_zero_int_override_survives_async_recalc_path(
    pg_dsn,
) -> None:
    """V2 fix end-to-end (int zero): a DataEntry persisted with
    ``__kg_co2eq_override__ = 0`` must produce an emission whose
    ``kg_co2eq`` equals ``0`` after the async ``upsert_by_data_entry``
    path — NOT the formula-derived value.

    Extends ``test_kg_co2eq_override_async_path_pg.py`` with a
    travel-plane shape (the actual API ingestion target).
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, _, module_id = await _seed_year_unit_and_module(
            s,
            institutional_id=f"OVR-INT-{uuid4().hex[:6]}",
        )
        await _seed_plane_locations(s)
        factor_id = await _seed_plane_factor(s)

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            carbon_report_module_id=module_id,
            data={
                "primary_factor_id": factor_id,
                "user_institutional_id": "U-API-0",
                "origin_iata": "GVA",
                "destination_iata": "CDG",
                "cabin_class": "economy",
                "number_of_trips": 1,
                # Override is the V2 boundary: int zero — a plane trip
                # someone manually corrected to 0 (e.g. cancelled).  Must
                # survive as 0.0 through the async recalc path.
                KG_CO2EQ_OVERRIDE_KEY: 0,
            },
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id: int = entry.id

    async with Sf() as s:
        e = (
            await s.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
        ).scalar_one()
        emission_svc = DataEntryEmissionService(s)
        await emission_svc.upsert_by_data_entry(DataEntryResponse.model_validate(e))
        await s.commit()

    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            rows = (
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
        assert len(rows) >= 1, (
            "expected ≥1 emission; if 0, the int-zero override silently "
            "disabled the override path (V2 regression)"
        )
        for r in rows:
            assert r.kg_co2eq == pytest.approx(0.0, abs=1e-9), (
                f"int-zero override leaked through: emission_id={r.id} "
                f"kg_co2eq={r.kg_co2eq}"
            )
            # Override branch — primary_factor_id stays None.
            assert r.primary_factor_id is None, (
                f"override row should have primary_factor_id=None; got "
                f"{r.primary_factor_id}"
            )
    finally:
        await verify_engine.dispose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_kg_co2eq_zero_float_override_survives_async_recalc_path(
    pg_dsn,
) -> None:
    """V2 fix end-to-end (float zero): mirror of the int-zero test,
    pinning that ``__kg_co2eq_override__ = 0.0`` (the type
    ``ProfessionalTravelApiProvider._load_data`` writes after the
    ``float()`` coercion) survives the async path.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        _, _, module_id = await _seed_year_unit_and_module(
            s,
            institutional_id=f"OVR-FLOAT-{uuid4().hex[:6]}",
        )
        await _seed_plane_locations(s)
        factor_id = await _seed_plane_factor(s)

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            carbon_report_module_id=module_id,
            data={
                "primary_factor_id": factor_id,
                "user_institutional_id": "U-API-1",
                "origin_iata": "GVA",
                "destination_iata": "CDG",
                "cabin_class": "economy",
                "number_of_trips": 1,
                KG_CO2EQ_OVERRIDE_KEY: 0.0,
            },
        )
        s.add(entry)
        await s.commit()
        assert entry.id is not None
        entry_id: int = entry.id

    async with Sf() as s:
        e = (
            await s.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
        ).scalar_one()
        emission_svc = DataEntryEmissionService(s)
        await emission_svc.upsert_by_data_entry(DataEntryResponse.model_validate(e))
        await s.commit()

    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            rows = (
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
        assert len(rows) >= 1
        for r in rows:
            assert r.kg_co2eq == pytest.approx(0.0, abs=1e-9), (
                f"float-zero override leaked through: emission_id={r.id} "
                f"kg_co2eq={r.kg_co2eq}"
            )
            assert r.primary_factor_id is None
    finally:
        await verify_engine.dispose()
        await engine.dispose()
