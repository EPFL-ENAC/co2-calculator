"""Background task for unit + principal-user synchronization with Accred API.

Plan 310B Part 5 — unit_sync is now a tracked DataIngestionJob (job_type=
unit_sync, entity_type=GLOBAL_PER_YEAR).  The endpoint creates the job
synchronously and returns its id; this task claims it via Plan 310A's
``claim_job`` and updates ``status_message`` between steps so the SSE stream
shows progress.
"""

from typing import Any, Dict

from pydantic import BaseModel

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_ingestion import IngestionResult, IngestionState
from app.models.user import UserProvider
from app.providers.role_provider import get_role_provider
from app.providers.unit_provider import get_unit_provider
from app.repositories.data_ingestion import DataIngestionRepository
from app.schemas.carbon_report import CarbonReportCreate
from app.services.carbon_report_service import CarbonReportService
from app.services.unit_service import UnitService
from app.services.user_service import UserService
from app.tasks._pod_id import POD_ID

logger = get_logger(__name__)


class SyncUnitRequest(BaseModel):
    target_year: int


async def run_sync_task_accred(
    sync_request: SyncUnitRequest,
    job_id: int,
) -> None:
    """Run the Accred unit + principal-user sync as a tracked job.

    Dual session — mirrors ``ingestion_tasks.run_sync_task``:

    - ``job_session`` commits ``status_message`` updates immediately so the
      SSE stream reflects progress.
    - ``data_session`` writes units / users / carbon reports inside one
      atomic transaction; rolled back as a unit on failure.

    Claim via ``claim_job`` ensures pod safety (Plan 310A): if two pods race
    on the same job_id, only one wins and the other returns silently.
    """
    target_year = sync_request.target_year

    async with SessionLocal() as job_session, SessionLocal() as data_session:
        job_repo = DataIngestionRepository(job_session)

        claimed = await job_repo.claim_job(job_id, POD_ID)
        if not claimed:
            logger.info(
                f"Unit sync job {job_id} already claimed or not eligible — skipping"
            )
            return

        try:
            await job_repo.update_ingestion_job(
                job_id=job_id,
                status_message="Fetching units from Accred…",
                metadata={},
            )
            await job_session.commit()

            unit_provider = get_unit_provider(UserProvider.ACCRED)
            role_provider = get_role_provider(UserProvider.ACCRED)
            units_raw, principal_users_raw = await unit_provider.fetch_all_units()

            units = [unit_provider.map_api_unit(u) for u in units_raw]
            principal_users = [
                role_provider.map_api_user(u) for u in principal_users_raw
            ]

            await job_repo.update_ingestion_job(
                job_id=job_id,
                status_message=(
                    f"Upserting {len(units)} units and "
                    f"{len(principal_users)} principal users…"
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
                job_id=job_id,
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
            new_carbon_reports = await carbon_report_service.bulk_upsert(
                report_create_data
            )

            await job_repo.update_ingestion_job(
                job_id=job_id,
                status_message=(
                    f"Ensuring modules for {len(new_carbon_reports)} carbon reports…"
                ),
                metadata={},
            )
            await job_session.commit()

            await carbon_report_service.ensure_modules_for_reports(new_carbon_reports)
            await data_session.commit()

            result_summary: Dict[str, Any] = {
                "units_synced": len(units),
                "users_synced": len(principal_users),
                "unit_results": str(unit_upsert_result),
                "user_results": str(user_upsert_result),
                "carbon_reports_created": len(new_carbon_reports),
                "carbon_report_year": target_year,
            }
            await job_repo.update_ingestion_job(
                job_id=job_id,
                status_message="Unit sync completed",
                metadata=result_summary,
                state=IngestionState.FINISHED,
                result=IngestionResult.SUCCESS,
            )
            await job_session.commit()
            logger.info(f"Unit sync job {job_id} completed: {result_summary}")
        except Exception as exc:
            logger.error(f"Unit sync job {job_id} failed: {exc}", exc_info=True)
            await data_session.rollback()
            await job_repo.update_ingestion_job(
                job_id=job_id,
                status_message=str(exc),
                metadata={"error": str(exc)},
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
            )
            await job_session.commit()
            # Do not re-raise: the endpoint schedules this task via
            # ``fire_and_forget`` (no awaiter), so a re-raise would
            # surface as "Task exception was never retrieved" warnings
            # on every failure.  The job state + status_message already
            # carry the error for operators / SSE consumers.
            return
