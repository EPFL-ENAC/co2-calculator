"""Background task for unit + principal-user synchronization with Accred API.

Plan 310B Part 5 — unit_sync is now a tracked DataIngestionJob (job_type=
unit_sync, entity_type=GLOBAL_PER_YEAR).  Plan 310-C cutover: the
``unit_sync_handler`` is the only entry point — endpoints fire it via
``run_job(id)``; the runner drives claim, heartbeat, and FINISHED state.
"""

from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionResult,
)
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration
from app.providers.role_provider import get_role_provider
from app.providers.unit_provider import get_unit_provider
from app.repositories.data_ingestion import DataIngestionRepository
from app.schemas.carbon_report import CarbonReportCreate
from app.services.carbon_report_service import CarbonReportService
from app.services.unit_service import UnitService
from app.services.user_service import UserService
from app.tasks.registry import register

logger = get_logger(__name__)


class SyncUnitRequest(BaseModel):
    target_year: int


@register("unit_sync")
async def unit_sync_handler(
    job: DataIngestionJob,
    job_session: AsyncSession,
    data_session: AsyncSession,
) -> dict:
    """Plan 310-C handler — Accred unit + principal-user sync.

    Reads ``target_year`` from ``job.meta['config']['target_year']``
    (set by the endpoint that creates the job; the safety poller's
    ``unit_sync`` branch reads the same path).  The runner has already
    claimed the job; this handler does the work and returns the meta
    dict the runner persists alongside the FINISHED state-write.

    Additive in this PR — coexists with ``run_sync_task_accred``
    until the endpoint+poller cutover removes the legacy function.
    """
    if job.id is None:
        raise ValueError("unit_sync: job has no id")

    config = (job.meta or {}).get("config") or {}
    target_year = config.get("target_year") or job.year
    if target_year is None:
        raise ValueError(
            f"unit_sync job {job.id} missing config.target_year (and job.year)"
        )

    job_repo = DataIngestionRepository(job_session)

    await job_repo.update_ingestion_job(
        job_id=job.id,
        status_message="Fetching units from Accred…",
        metadata={},
    )
    await job_session.commit()

    unit_provider = get_unit_provider(UserProvider.ACCRED)
    role_provider = get_role_provider(UserProvider.ACCRED)
    units_raw, principal_users_raw = await unit_provider.fetch_all_units()

    units = [unit_provider.map_api_unit(u) for u in units_raw]
    principal_users = [role_provider.map_api_user(u) for u in principal_users_raw]

    await job_repo.update_ingestion_job(
        job_id=job.id,
        status_message=(
            f"Upserting {len(units)} units and {len(principal_users)} principal users…"
        ),
        metadata={},
    )
    await job_session.commit()

    unit_service = UnitService(data_session)
    unit_upsert_result = await unit_service.bulk_upsert(units)
    units = unit_upsert_result.data

    user_service = UserService(data_session)
    user_upsert_result = await user_service.bulk_upsert(principal_users)
    principal_users = user_upsert_result.data

    await job_repo.update_ingestion_job(
        job_id=job.id,
        status_message=f"Creating carbon reports for year {target_year}…",
        metadata={},
    )
    await job_session.commit()

    carbon_report_service = CarbonReportService(data_session)
    report_create_data = [
        CarbonReportCreate(year=target_year, unit_id=u.id)
        for u in units
        if u.id is not None
    ]
    new_carbon_reports = await carbon_report_service.bulk_upsert(report_create_data)

    await job_repo.update_ingestion_job(
        job_id=job.id,
        status_message=(
            f"Ensuring modules for {len(new_carbon_reports)} carbon reports…"
        ),
        metadata={},
    )
    await job_session.commit()

    await carbon_report_service.ensure_modules_for_reports(new_carbon_reports)

    # #1234-followup (Guilbert 2026-05-20): mark the year as provisioned
    # so /dispatch can gate uploads while a unit_sync is still running
    # or before it ever ran. data_session is the right session — the
    # runner commits it on handler success; failure paths raise and
    # data_session is rolled back so this stamp is atomic with the
    # carbon-reports/modules creation above.
    year_cfg_row = (
        await data_session.execute(
            select(YearConfiguration).where(col(YearConfiguration.year) == target_year)
        )
    ).scalar_one_or_none()
    if year_cfg_row is not None:
        year_cfg_row.configuration_completed = datetime.now(timezone.utc)
        data_session.add(year_cfg_row)
    else:
        logger.warning(
            "unit_sync: no YearConfiguration row for year=%s — "
            "configuration_completed stamp skipped (year-config row "
            "should exist; was the year created via /year-configurations?)",
            target_year,
        )

    return {
        "status_message": "Unit sync completed",
        "result": IngestionResult.SUCCESS,
        "units_synced": len(units),
        "users_synced": len(principal_users),
        "unit_results": str(unit_upsert_result),
        "user_results": str(user_upsert_result),
        "carbon_reports_created": len(new_carbon_reports),
        "carbon_report_year": target_year,
    }
