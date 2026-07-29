"""Bootstrap a freshly-created database from ``backend/INPUT_DATA``.

Replays, per year, the whole backoffice click-path that otherwise has to be
redone by hand after every ``make db-drop``:

1. create the ``year_configuration`` row (default config, every module on);
2. run the ``unit_sync`` pipeline — units + principal users from the unit
   provider, then ``carbon_reports`` + ``carbon_report_modules`` for the
   year, and the ``configuration_completed`` stamp that unblocks uploads;
3. ingest every factor CSV for that year;
4. ingest the reference CSVs (airports, train stations, building rooms);
5. load the three reduction-objective CSVs and the institutional goals;
6. open the year for end users (``is_started``).

Data entries are deliberately NOT seeded — the modules are left empty.
Use ``make seed-generic-data`` if you want rows too.
"""

import argparse
import asyncio
from datetime import datetime
from typing import Sequence
from uuid import uuid4

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import (
    ModuleTypeEnum,
    get_module_type_for_data_entry_type,
)
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration
from app.providers.unit_provider import get_unit_provider
from app.repositories.data_ingestion import DataIngestionRepository
from app.seed.seed_generic_factors import FACTOR_SEEDS, seed_all_factors
from app.seed.seed_reduction_objectives import seed_reduction_objectives
from app.seed.seed_reference_data import seed_all_reference_data
from app.services.year_config_service import generate_default_year_config
from app.tasks._background import wait_for_background_tasks
from app.tasks.runner import run_job

logger = get_logger(__name__)

DEFAULT_YEARS: tuple[int, ...] = (2025, 2026)


def _validate_year(year: int) -> None:
    """Reject years ``POST /year-configuration/{year}`` would refuse."""
    settings = get_settings()
    current_year = datetime.now().year
    if year < settings.MIN_CONFIGURABLE_YEAR or year > current_year:
        raise ValueError(
            f"Year {year} is out of range — must be between "
            f"{settings.MIN_CONFIGURABLE_YEAR} and {current_year}"
        )


async def _ensure_year_configuration(
    session: AsyncSession, year: int, provider: UserProvider
) -> None:
    """Create the year row if it does not exist yet (idempotent re-runs)."""
    stmt = select(YearConfiguration).where(
        col(YearConfiguration.year) == year,
        col(YearConfiguration.provider) == provider,
    )
    existing = (await session.exec(stmt)).first()
    if existing is not None:
        print(f"Year {year} ({provider.name}) already configured — reusing it")
        return

    session.add(
        YearConfiguration(
            year=year,
            provider=provider,
            is_started=False,
            config=generate_default_year_config(),
        )
    )
    await session.commit()
    print(f"Created year configuration {year} ({provider.name})")


async def _enqueue(job: DataIngestionJob, kind: str) -> int:
    """Persist a job under a fresh pipeline and return its id."""
    async with SessionLocal() as session:
        repo = DataIngestionRepository(session)
        pipeline_id = uuid4()
        job.pipeline_id = pipeline_id
        await repo.ensure_pipeline_exists(
            pipeline_id,
            kind=kind,
            entity_type=job.entity_type.value,
            ingestion_method=job.ingestion_method.value,
            module_type_id=job.module_type_id,
            year=job.year,
        )
        created = await repo.create_ingestion_job(job)
        await session.commit()
        if created.id is None:
            raise RuntimeError(f"{kind} job for {job.year} was not persisted")
        return created.id


async def _run_and_check(job_id: int, label: str) -> None:
    """Await ``run_job`` and fail loudly on an ERROR outcome.

    ``run_job`` turns handler failures into FINISHED+ERROR rather than
    raising, so the outcome has to be read back explicitly.
    """
    await run_job(job_id)
    async with SessionLocal() as session:
        finished = await DataIngestionRepository(session).get_job_by_id(job_id)
        if finished is None:
            raise RuntimeError(f"{label} job {job_id} disappeared")
        if finished.result is None or finished.result == IngestionResult.ERROR:
            raise RuntimeError(
                f"{label} job {job_id} ended {finished.state}/{finished.result} — "
                f"{finished.status_message}"
            )
        if finished.result != IngestionResult.SUCCESS:
            print(f"  {label}: {finished.result} — {finished.status_message}")


async def _run_unit_sync(year: int, provider: UserProvider) -> None:
    """Enqueue and await the ``unit_sync`` job for one year.

    Mirrors the job ``create_year_configuration`` enqueues, but awaits
    ``run_job`` instead of firing it in the background so the CLI blocks
    until the units, carbon reports and modules exist.
    """
    job_id = await _enqueue(
        DataIngestionJob(
            job_type="unit_sync",
            module_type_id=None,
            data_entry_type_id=None,
            year=year,
            ingestion_method=IngestionMethod.api,
            target_type=TargetType.REFERENCE_DATA,
            entity_type=EntityType.GLOBAL_PER_YEAR,
            state=IngestionState.NOT_STARTED,
            provider=provider,
            meta={"config": {"target_year": year}},
        ),
        kind="unit_sync",
    )
    print(f"Running unit_sync for {year} (job {job_id})…")
    await _run_and_check(job_id, f"unit_sync {year}")
    print(f"unit_sync for {year} finished")


def _seeded_types_by_module() -> dict[int, list[int]]:
    """Map every module the factor seeds touch to its data-entry types.

    Read off ``FACTOR_SEEDS`` rather than
    ``get_recalculation_status_by_year``: a multi-type CSV (equipment,
    purchases_common) plants its stub job with ``data_entry_type_id=NULL``,
    and that query filters NULLs out — so the status rows do not name every
    type that just got new factors.
    """
    by_module: dict[int, list[int]] = {}
    for config in FACTOR_SEEDS:
        for det in config.data_entry_types:
            module_type = get_module_type_for_data_entry_type(det)
            if module_type is None:
                raise ValueError(
                    f"Cannot determine module_type for data_entry_type: {det.name}"
                )
            types = by_module.setdefault(module_type.value, [])
            if det.value not in types:
                types.append(det.value)
    return by_module


async def _run_emission_recalculations(year: int, provider: UserProvider) -> None:
    """Recalculate emissions per module, as a factor upload's chain would.

    Seeded factors go in through ``LocalFactorCSVProvider``, which bypasses
    ``factor_ingest`` and therefore never fans out the ``emission_recalc``
    children.  Without them the backoffice configuration page shows
    "Recalculation needed" on every module: ``get_recalculation_status_by_year``
    flags a type whose latest FACTORS job is newer than its latest computed
    DATA_ENTRIES job.  This replays
    ``POST /sync/recalculate-emissions/{module_type_id}`` per module, whose
    handler also writes the per-type stub jobs that query matches on.
    """
    for module_type_id, det_ids in _seeded_types_by_module().items():
        job_id = await _enqueue(
            DataIngestionJob(
                job_type="module_emission_recalc",
                module_type_id=module_type_id,
                data_entry_type_id=None,
                year=year,
                ingestion_method=IngestionMethod.computed,
                target_type=TargetType.DATA_ENTRIES,
                entity_type=EntityType.MODULE_PER_YEAR,
                state=IngestionState.NOT_STARTED,
                provider=provider,
                meta={
                    "config": {
                        "year": year,
                        "data_entry_type_ids": det_ids,
                        "only_stale": False,
                    }
                },
            ),
            kind="module_emission_recalc",
        )
        label = ModuleTypeEnum(module_type_id).name
        await _run_and_check(job_id, f"recalc {label} {year}")
        print(f"Recalculated {label} ({len(det_ids)} types) for {year}")

    # Each module recalc chains an ``aggregation`` child through
    # ``fire_and_forget``.  A CLI has to wait for those before the loop
    # closes, or they are cancelled mid-run and left stuck in RUNNING.
    await wait_for_background_tasks()


async def _open_year(session: AsyncSession, year: int, provider: UserProvider) -> None:
    stmt = select(YearConfiguration).where(
        col(YearConfiguration.year) == year,
        col(YearConfiguration.provider) == provider,
    )
    row = (await session.exec(stmt)).first()
    if row is None:
        raise ValueError(f"No year_configuration row for year={year}")
    row.is_started = True
    session.add(row)


async def bootstrap_year(year: int, provider: UserProvider) -> None:
    """Run the full bootstrap for a single year."""
    _validate_year(year)
    print(f"\n=== Bootstrapping {year} ({provider.name}) ===")

    async with SessionLocal() as session:
        await _ensure_year_configuration(session, year, provider)

    await _run_unit_sync(year, provider)

    async with SessionLocal() as session:
        await seed_all_factors(session, year)
        await seed_all_reference_data(session, year)

    await _run_emission_recalculations(year, provider)

    async with SessionLocal() as session:
        await seed_reduction_objectives(session, year, provider)
        await _open_year(session, year, provider)
        await session.commit()

    print(f"=== {year} ready ===")


async def main(years: Sequence[int] = DEFAULT_YEARS) -> None:
    provider = get_unit_provider().type
    for year in years:
        await bootstrap_year(year, provider)
    print(f"\nBootstrapped years: {', '.join(str(y) for y in years)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=list(DEFAULT_YEARS),
        help="Years to bootstrap (default: 2025 2026)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.years))
