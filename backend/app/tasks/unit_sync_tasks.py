"""Background tasks for unit synchronization with Accred API."""

import asyncio
from typing import Any, Dict

from pydantic import BaseModel

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.user import UserProvider
from app.providers.role_provider import get_role_provider
from app.providers.unit_provider import get_unit_provider
from app.schemas.carbon_report import CarbonReportCreate
from app.services.carbon_report_service import CarbonReportService
from app.services.unit_service import UnitService
from app.services.user_service import UserService

logger = get_logger(__name__)


class SyncUnitRequest(BaseModel):
    target_year: int


async def run_sync_task_accred(syncRequest: SyncUnitRequest) -> Dict[str, Any]:
    """
    Background task to sync units and principal users from Accred API.

    This task:
    1. Fetches all units from Accred API
    2. Bulk upserts units into database
    3. Fetches and upserts principal users
    4. Commits changes
    5. Create all carbon reports for all units (one per unit, using target_year)
    6. All corresponding carbon_reports_modules are auto-created by service

    Args:
        target_year: The year for carbon reports (required)

    Returns:
        Dict with sync results including counts and status
    """
    target_year = syncRequest.target_year

    try:
        logger.info("Starting unit sync from Accred API")

        async with SessionLocal() as session:
            carbon_reports_created = 0
            # Get providers
            provider = get_unit_provider(UserProvider.ACCRED)
            role_provider = get_role_provider(UserProvider.ACCRED)

            # Fetch data from Accred API
            units_raw, principal_users_raw = await provider.fetch_all_units()

            # Map API responses to domain models
            units = [provider.map_api_unit(unit) for unit in units_raw]
            principal_users = [
                role_provider.map_api_user(user) for user in principal_users_raw
            ]

            logger.info(
                f"Fetched {len(units)} units and "
                f"{len(principal_users)} principal users from Accred API"
            )

            unit_service = UnitService(session)
            unit_upsert_result = await unit_service.bulk_upsert(units)
            units = unit_upsert_result.data

            carbon_report_service = CarbonReportService(session)

            user_service = UserService(session)
            user_upsert_result = await user_service.bulk_upsert(principal_users)
            principal_users = user_upsert_result.data

            try:
                report_create_data = [
                    CarbonReportCreate(year=target_year, unit_id=unit.id)
                    for unit in units
                    if unit.id is not None
                ]
                new_carbon_reports = await carbon_report_service.bulk_upsert(
                    report_create_data
                )
                carbon_reports_created = len(new_carbon_reports)

                logger.info(
                    f"Upserted {carbon_reports_created} carbon reports "
                    f"for {len(units)} units"
                )

                await carbon_report_service.ensure_modules_for_reports(
                    new_carbon_reports
                )
                logger.info(
                    f"Ensured modules for {len(new_carbon_reports)} carbon reports"
                )

                await session.commit()

            except Exception as e:
                logger.error(f"Failed to create carbon reports: {e}", exc_info=True)
                await session.rollback()
                raise

            result = {
                "status": "success",
                "units_synced": len(units),
                "users_synced": len(principal_users),
                "unit_results": str(unit_upsert_result),
                "user_results": str(user_upsert_result),
                "carbon_reports_created": carbon_reports_created,
                "carbon_report_year": target_year,
            }

            logger.info(f"Unit sync completed successfully: {result}")
            return result

    except Exception as e:
        logger.error(f"Unit sync from Accred API failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


# @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
# add self to make it celery compatible
def sync_units_from_accred_task(syncRequest: SyncUnitRequest):
    """almost celery compatible sync wrapper for run_sync_task"""
    try:
        asyncio.run(run_sync_task_accred(syncRequest))
    except Exception:
        logger.error(f"Sync failed for sync request: {syncRequest}", exc_info=True)
        # Error already logged and job status updated in run_sync_task
        raise  # propagate exception for Celery retry
