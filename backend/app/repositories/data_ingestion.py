import enum
from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import col, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    IngestionResult,
    IngestionState,
    IngestionStatus,
)


class DataIngestionRepository:
    """Repository for DataIngestionJob database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_ingestion_job(
        self,
        data: DataIngestionJob,
    ) -> DataIngestionJob:
        job = DataIngestionJob.model_validate(data)
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    def sanitize_for_json(self, obj):
        if isinstance(obj, dict):
            return {
                k: self.sanitize_for_json(v)
                for k, v in obj.items()
                if not k.startswith("_") and k != "_sa_instance_state"
            }
        elif isinstance(obj, list):
            return [self.sanitize_for_json(i) for i in obj]
        elif isinstance(obj, enum.Enum):
            return obj.value
        else:
            return obj

    async def update_ingestion_job(
        self,
        job_id: int,
        status_message: str,
        status_code: IngestionStatus,
        metadata: dict,
        completed_at: Optional[datetime] = None,
        state: Optional[IngestionState] = None,
        result: Optional[IngestionResult] = None,
    ) -> Optional[DataIngestionJob]:
        """Update ingestion job with legacy status_code and new state/result.

        Args:
            job_id: Job ID to update
            status_message: Status message
            status_code: Legacy status code (for backward compatibility)
            metadata: Metadata to merge
            completed_at: Optional completed timestamp
            state: New state value (optional, for new code)
            result: New result value (optional, for new code)
        """
        stmt = select(DataIngestionJob).where(DataIngestionJob.id == job_id)
        exec_result = await self.session.execute(stmt)
        result_job = exec_result.scalar_one_or_none()
        if not result_job:
            return None

        if result_job:
            DataIngestionJob.model_validate(result_job)

            result_job.status_message = status_message
            result_job.status = status_code
            # Use new state/result if provided, otherwise derive from legacy status_code
            if state is not None:
                result_job.state = state
            else:
                result_job.state = self._legacy_status_to_state(status_code)
            if result is not None:
                result_job.result = result
            else:
                result_job.result = self._legacy_status_to_result(status_code)

            merged_meta = {
                **self.sanitize_for_json(result_job.meta or {}),
                **self.sanitize_for_json(metadata or {}),
                "completed_at": (
                    completed_at.isoformat()
                    if completed_at
                    else (
                        datetime.now(timezone.utc).isoformat()
                        if status_code in (IngestionStatus.COMPLETED, IngestionStatus.FAILED)
                        else None
                    )
                ),
            }
            result_job.meta = merged_meta
            await self.session.flush()
            await self.session.refresh(result_job)
        return result_job

    def _legacy_status_to_state(self, status_code: IngestionStatus) -> IngestionState:
        """Convert legacy IngestionStatus to new IngestionState."""
        mapping = {
            IngestionStatus.NOT_STARTED: IngestionState.NOT_STARTED,
            IngestionStatus.PENDING: IngestionState.QUEUED,
            IngestionStatus.IN_PROGRESS: IngestionState.RUNNING,
            IngestionStatus.COMPLETED: IngestionState.FINISHED,
            IngestionStatus.FAILED: IngestionState.FINISHED,
        }
        return mapping.get(status_code, IngestionState.NOT_STARTED)

    def _legacy_status_to_result(self, status_code: IngestionStatus) -> Optional[IngestionResult]:
        """Convert legacy IngestionStatus to new IngestionResult (None for non-finished states)."""
        if status_code == IngestionStatus.COMPLETED:
            return IngestionResult.SUCCESS
        if status_code == IngestionStatus.FAILED:
            return IngestionResult.ERROR
        return None

    async def get_job_by_id(self, job_id: int) -> Optional[DataIngestionJob]:
        stmt = select(DataIngestionJob).where(DataIngestionJob.id == job_id)
        exec_result = await self.session.execute(stmt)
        job = exec_result.scalar_one_or_none()
        if job:
            await self.session.refresh(job)
        return job

    async def get_jobs_by_year(self, year: int) -> List[DataIngestionJob]:
        stmt = select(DataIngestionJob).where(DataIngestionJob.year == year)
        stmt = stmt.order_by(col(DataIngestionJob.id).desc())
        exec_result = await self.session.execute(stmt)
        return list(exec_result.scalars().all())

    async def _get_jobs_by_state(
        self, states: list[IngestionState], negate: bool = False
    ) -> list[DataIngestionJob]:
        """
        Helper method to fetch jobs filtered by state.

        Args:
            states: List of IngestionState values to filter by
            negate: If True, exclude jobs with these states (use notin_)

        Returns:
            List of DataIngestionJob objects ordered by id descending
        """
        state_filter = (
            col(DataIngestionJob.state).notin_(states)
            if negate
            else col(DataIngestionJob.state).in_(states)
        )
        stmt = (
            select(DataIngestionJob)
            .where(state_filter)
            .order_by(desc(DataIngestionJob.id))
        )
        exec_result = await self.session.execute(stmt)
        return list(exec_result.scalars().all())

    async def get_finished_jobs(self) -> list[DataIngestionJob]:
        """
        Get all jobs that are in a finished state.
        """
        return await self._get_jobs_by_state([IngestionState.FINISHED])

    async def get_active_jobs(self) -> list[DataIngestionJob]:
        """
        Get all jobs that are not in a finished state.
        Used for SSE streaming of job updates.
        """
        return await self._get_jobs_by_state([IngestionState.FINISHED], negate=True)
