import enum
from datetime import datetime
from typing import List, Optional

from sqlmodel import col, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import DataIngestionJob, IngestionStatus


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
        await self.session.commit()
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
    ) -> Optional[DataIngestionJob]:
        stmt = select(DataIngestionJob).where(DataIngestionJob.id == job_id)
        result = await self.session.execute(stmt)
        result_job = result.scalar_one_or_none()
        if not result_job:
            return None

        if result_job:
            DataIngestionJob.model_validate(result_job)

            result_job.status_message = status_message
            result_job.status = status_code
            merged_meta = {
                **self.sanitize_for_json(result_job.meta or {}),
                **self.sanitize_for_json(metadata or {}),
                "completed_at": (
                    completed_at.isoformat()
                    if completed_at
                    else (
                        datetime.utcnow().isoformat()
                        if status_code == IngestionStatus.COMPLETED
                        else None
                    )
                ),
            }
            result_job.meta = merged_meta
            await self.session.commit()
            await self.session.refresh(result_job)
        return result_job

    async def get_job_by_id(self, job_id: int) -> Optional[DataIngestionJob]:
        stmt = select(DataIngestionJob).where(DataIngestionJob.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_jobs_by_year(self, year: int) -> List[DataIngestionJob]:
        stmt = select(DataIngestionJob).where(DataIngestionJob.year == year)
        stmt = stmt.order_by(col(DataIngestionJob.id).desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_jobs(self) -> list[DataIngestionJob]:
        """
        Get all jobs that are not in a final state (not COMPLETED or FAILED).
        Used for SSE streaming of job updates.
        """
        final_states = [IngestionStatus.COMPLETED, IngestionStatus.FAILED]

        stmt = (
            select(DataIngestionJob)
            .where(
                # 1. Use 'col()' to satisfy Mypy
                # 2. Use 'notin_' (with the underscore)
                col(DataIngestionJob.status).notin_(final_states)
            )
            # 3. use desc(DataIngestionJob.id)
            .order_by(desc(DataIngestionJob.id))
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
