"""Background tasks for emission recalculation.

Mirrors the dual-session pattern from ingestion_tasks.py:
- job_session: frequent commits for SSE progress visibility
- data_session: single atomic commit at the end
"""

import asyncio
import logging

from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.repositories.data_ingestion import DataIngestionRepository
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Single-type variant
# ---------------------------------------------------------------------------


async def run_recalculation_task(
    module_type_id: int,
    data_entry_type_id: int,
    year: int,
    job_id: int,
) -> None:
    """Async implementation of single data_entry_type recalculation.

    Uses two sessions:
    - job_session: commits status updates immediately (visible to SSE)
    - data_session: single atomic commit after all emissions are upserted

    Args:
        module_type_id: The module type being recalculated.
        data_entry_type_id: The data entry type to recalculate.
        year: The report year to scope the recalculation.
        job_id: The DataIngestionJob id to update with progress.
    """
    async with SessionLocal() as job_session, SessionLocal() as data_session:
        job_repo = DataIngestionRepository(job_session)
        job = await job_repo.get_job_by_id(job_id)
        if not job:
            logger.error(f"Recalculation job {job_id} not found.")
            return

        # Mark as running
        await job_repo.update_ingestion_job(
            job_id=job_id,
            status_message="Starting emission recalculation...",
            metadata={},
            state=IngestionState.RUNNING,
        )
        job = await job_repo.get_job_by_id(job_id)
        if job:
            await job_repo.mark_job_as_current(job)
        await job_session.commit()

        try:
            data_entry_type = DataEntryTypeEnum(data_entry_type_id)
            svc = EmissionRecalculationWorkflow(data_session)

            await job_repo.update_ingestion_job(
                job_id=job_id,
                status_message="Recalculating emissions...",
                metadata={},
                state=IngestionState.RUNNING,
            )
            await job_session.commit()

            stats = await svc.recalculate_for_data_entry_type(data_entry_type, year)

            # Commit the data session atomically
            await data_session.commit()

            result = (
                IngestionResult.SUCCESS
                if stats["errors"] == 0
                else IngestionResult.WARNING
            )
            await job_repo.update_ingestion_job(
                job_id=job_id,
                status_message="Emission recalculation completed",
                metadata={"recalculation": stats},
                state=IngestionState.FINISHED,
                result=result,
            )
            await job_session.commit()
            logger.info(f"Recalculation job {job_id} finished: {stats}")

        except Exception as exc:
            logger.error(f"Recalculation job {job_id} failed: {exc}", exc_info=True)
            await data_session.rollback()
            await job_repo.update_ingestion_job(
                job_id=job_id,
                status_message=str(exc),
                metadata={},
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
            )
            await job_session.commit()


def run_recalculation(
    module_type_id: int,
    data_entry_type_id: int,
    year: int,
    job_id: int,
) -> None:
    """Sync wrapper for run_recalculation_task (FastAPI BackgroundTasks compatible).

    Args:
        module_type_id: The module type being recalculated.
        data_entry_type_id: The data entry type to recalculate.
        year: The report year.
        job_id: Job id to update.
    """
    try:
        asyncio.run(
            run_recalculation_task(module_type_id, data_entry_type_id, year, job_id)
        )
    except Exception as exc:
        logger.error(f"run_recalculation failed for job {job_id}: {exc}")
        raise


# ---------------------------------------------------------------------------
# Module-level (multi-type) variant
# ---------------------------------------------------------------------------


async def run_module_recalculation_task(
    module_type_id: int,
    data_entry_type_ids: list[int],
    year: int,
    job_id: int,
) -> None:
    """Async implementation of module-level bulk recalculation.

    Iterates over all requested data_entry_type_ids in sequence.  A single
    failing type never aborts the others — errors are accumulated in per-type
    stats.  data_session is committed once after all types are done
    (all-or-nothing for the whole module).

    Final job result:
    - SUCCESS if no errors across all types
    - WARNING if any type had partial errors
    - ERROR only if every type failed entirely

    Args:
        module_type_id: The module type being recalculated.
        data_entry_type_ids: Ordered list of data entry type IDs to process.
        year: The report year.
        job_id: Job id to update.
    """
    async with SessionLocal() as job_session, SessionLocal() as data_session:
        job_repo = DataIngestionRepository(job_session)
        job = await job_repo.get_job_by_id(job_id)
        if not job:
            logger.error(f"Module recalculation job {job_id} not found.")
            return

        await job_repo.update_ingestion_job(
            job_id=job_id,
            status_message="Starting module emission recalculation...",
            metadata={},
            state=IngestionState.RUNNING,
        )
        job = await job_repo.get_job_by_id(job_id)
        if job:
            await job_repo.mark_job_as_current(job)
        await job_session.commit()

        n = len(data_entry_type_ids)
        per_type_stats: dict[int, dict] = {}
        total_errors = 0
        total_recalculated = 0

        try:
            svc = EmissionRecalculationWorkflow(data_session)

            for i, det_id in enumerate(data_entry_type_ids, start=1):
                data_entry_type = DataEntryTypeEnum(det_id)
                await job_repo.update_ingestion_job(
                    job_id=job_id,
                    status_message=(
                        f"Recalculating {data_entry_type.name} ({i}/{n})..."
                    ),
                    metadata={},
                    state=IngestionState.RUNNING,
                )
                await job_session.commit()

                try:
                    stats = await svc.recalculate_for_data_entry_type(
                        data_entry_type, year
                    )
                    per_type_stats[det_id] = stats
                    total_errors += stats["errors"]
                    total_recalculated += stats["recalculated"]
                except Exception as exc:
                    logger.error(
                        f"Module recalculation job {job_id}: type {det_id} "
                        f"failed entirely: {exc}",
                        exc_info=True,
                    )
                    # Count the entire type as failed
                    per_type_stats[det_id] = {
                        "recalculated": 0,
                        "modules_refreshed": 0,
                        "errors": -1,  # -1 signals a fatal type-level error
                        "error_details": [{"error": str(exc)}],
                    }
                    total_errors += 1

            # Commit data session once (all-or-nothing for the whole module)
            await data_session.commit()

            # Determine overall result
            types_with_fatal = [
                det_id for det_id, s in per_type_stats.items() if s["errors"] == -1
            ]
            if len(types_with_fatal) == n:
                final_result = IngestionResult.ERROR
            elif total_errors > 0:
                final_result = IngestionResult.WARNING
            else:
                final_result = IngestionResult.SUCCESS

            # Create per-type stub jobs so recalc_jobs_sub can match them.
            # The module-level job has data_entry_type_id=None, which is excluded
            # by get_recalculation_status_by_year; individual jobs are required.
            for det_id, stats in per_type_stats.items():
                if stats["errors"] == -1:
                    type_result = IngestionResult.ERROR
                elif stats["errors"] > 0:
                    type_result = IngestionResult.WARNING
                else:
                    type_result = IngestionResult.SUCCESS
                type_job = DataIngestionJob(
                    module_type_id=module_type_id,
                    data_entry_type_id=det_id,
                    year=year,
                    ingestion_method=IngestionMethod.computed,
                    target_type=TargetType.DATA_ENTRIES,
                    entity_type=EntityType.MODULE_PER_YEAR,
                    state=IngestionState.FINISHED,
                    result=type_result,
                    status_message=f"Bulk recalculation via module job {job_id}",
                    meta={"parent_job_id": job_id, "recalculation": stats},
                )
                created_type_job = await job_repo.create_ingestion_job(type_job)
                await job_repo.mark_job_as_current(created_type_job)

            await job_repo.update_ingestion_job(
                job_id=job_id,
                status_message="Module emission recalculation completed",
                metadata={"recalculation": per_type_stats},
                state=IngestionState.FINISHED,
                result=final_result,
            )
            await job_session.commit()
            logger.info(
                f"Module recalculation job {job_id} finished: "
                f"recalculated={total_recalculated}, errors={total_errors}"
            )

        except Exception as exc:
            logger.error(
                f"Module recalculation job {job_id} outer failure: {exc}",
                exc_info=True,
            )
            await data_session.rollback()
            await job_repo.update_ingestion_job(
                job_id=job_id,
                status_message=str(exc),
                metadata={},
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
            )
            await job_session.commit()


def run_module_recalculation(
    module_type_id: int,
    data_entry_type_ids: list[int],
    year: int,
    job_id: int,
) -> None:
    """Sync wrapper for run_module_recalculation_task.

    Args:
        module_type_id: The module type being recalculated.
        data_entry_type_ids: Data entry type IDs to process.
        year: The report year.
        job_id: Job id to update.
    """
    try:
        asyncio.run(
            run_module_recalculation_task(
                module_type_id, data_entry_type_ids, year, job_id
            )
        )
    except Exception as exc:
        logger.error(f"run_module_recalculation failed for job {job_id}: {exc}")
        raise
