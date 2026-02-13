from abc import ABC, abstractmethod
from asyncio.log import logger
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    FactorType,
    IngestionMethod,
    IngestionStatus,
    TargetType,
)
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository


class DataIngestionProvider(ABC):
    def __init__(
        self,
        config: Dict[str, Any],
        user: User | None = None,
        job_session: AsyncSession | None = None,
        *,
        data_session: AsyncSession,
    ):
        self.config = config or {}
        self.user = user
        self.job_session = job_session  # For job status updates (frequent commits)
        self.data_session = data_session  # For data operations (atomic commit)
        self.job_id: Optional[int] = None
        self.job: Optional[DataIngestionJob] = None

    async def set_job_id(self, job_id: int):
        self.job_id = job_id

    @abstractmethod
    async def validate_connection(self) -> bool:
        pass

    @abstractmethod
    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def transform_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass

    async def create_job(
        self,
        module_type_id: ModuleTypeEnum,
        data_entry_type_id: Optional[int],
        ingestion_method: IngestionMethod,
        entity_type: EntityType,
        target_type: TargetType,
        year: Optional[int] = None,
        factor_type_id: FactorType | None = None,
        config: Dict[str, Any] | None = None,
        db: AsyncSession | None = None,
    ) -> int:
        """Create an ingestion job.

        Args:
            db: Optional database session. If provided, uses this session and caller
                is responsible for committing. If not provided, creates a new session
                and commits within this method.
        """
        if db is None:
            raise ValueError("Database session is required to create ingestion job")
        # Use provided session - caller is responsible for commit
        repo = DataIngestionRepository(db)
        job_config = config or {}
        job_config["entity_type"] = entity_type.value
        # Merge config into self.config so it's preserved for later use
        self.config.update(job_config)
        meta = {
            "factor_type_id": factor_type_id.value if factor_type_id else None,
            "config": job_config,  # Store entire config in meta for job
        }

        data = DataIngestionJob(
            module_type_id=module_type_id,
            ingestion_method=ingestion_method,
            data_entry_type_id=data_entry_type_id,
            entity_type=entity_type,
            target_type=target_type,
            status=IngestionStatus.NOT_STARTED,
            status_message="Job created",
            meta=meta,
            provider=self.user.provider if self.user else None,
            year=year,
        )
        job = await repo.create_ingestion_job(data)
        if not job:
            raise Exception("Failed to create ingestion job")
        self.job_id = job.id
        self.job = job
        if self.job_id is None:
            raise Exception("Failed to create ingestion job id")

        # Create audit record for job creation
        from app.models.audit import AuditChangeTypeEnum
        from app.services.audit_service import AuditDocumentService

        audit_service = AuditDocumentService(db)
        changed_by = self.user.id if self.user else self.job_id
        handler_id = self.user.provider_code if self.user else "csv_ingestion"

        await audit_service.create_version(
            entity_type="DataIngestionJob",
            entity_id=self.job_id,
            data_snapshot=job.model_dump(),
            change_type=AuditChangeTypeEnum.CREATE,
            changed_by=changed_by,
            change_reason=f"Data ingestion job created via {ingestion_method.value}",
            handler_id=handler_id,
            handled_ids=[],  # No specific handled IDs for job creation
            ip_address=None,
            route_path=None,
            route_payload=None,
        )

        return self.job_id

    async def ingest(
        self,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        try:
            await self._update_job(
                status_message="processing",
                status_code=IngestionStatus.IN_PROGRESS,
                extra_metadata={"message": "Starting sync..."},
            )
            raw_data = await self.fetch_data(filters or {})
            await self._update_job(
                status_message="processing",
                status_code=IngestionStatus.IN_PROGRESS,
                extra_metadata={"message": f"Fetched {len(raw_data)} records"},
            )
            transformed_data = await self.transform_data(raw_data)
            await self._update_job(
                status_message="processing",
                status_code=IngestionStatus.IN_PROGRESS,
                extra_metadata={"message": "Transforming data..."},
            )
            result = await self._load_data(transformed_data)
            await self._update_job(
                status_message="completed",
                status_code=IngestionStatus.COMPLETED,
                extra_metadata={
                    "message": f"Successfully processed {result['inserted']} records"
                },
            )
            return {
                "status_code": IngestionStatus.COMPLETED,
                "status_message": "Success",
                "data": result,
            }
        except Exception as e:
            await self._update_job(
                status_message=f"failed: {str(e)}",
                status_code=IngestionStatus.FAILED,
                extra_metadata={"error": str(e)},
            )
            logger.error(f"Ingestion failed: {str(e)}")
            raise

    async def _update_job(
        self,
        status_message: str,
        status_code: IngestionStatus,
        extra_metadata: dict | None = None,
    ):
        metadata = {"config": self.config}
        if extra_metadata:
            metadata.update(extra_metadata)
        if not self.job_id:
            logger.warning("Job ID is not set. Cannot update ingestion job.")
            return
        if not self.job_session:
            logger.warning("No job session available. Cannot update ingestion job.")
            return

        repo = DataIngestionRepository(self.job_session)
        await repo.update_ingestion_job(
            job_id=self.job_id,
            status_message=status_message,
            status_code=status_code,
            metadata=metadata,
            completed_at=datetime.utcnow()
            if status_code in [IngestionStatus.COMPLETED, IngestionStatus.FAILED]
            else None,
        )
        # Commit immediately so SSE endpoints can see the update
        await self.job_session.commit()

    async def _update_job_and_sync(
        self,
        repo: DataIngestionRepository,
        job_id: int,
        status_message: str,
        status_code: IngestionStatus,
        metadata: dict | None = None,
        completed_at: datetime | None = None,
    ) -> Optional[DataIngestionJob]:
        """
        Update ingestion job and keep self.job in sync.
        Use when working with an existing repository/session
        (e.g., in self.data_session).
        Returns the updated job object.
        """
        updated_job = await repo.update_ingestion_job(
            job_id=job_id,
            status_message=status_message,
            status_code=status_code,
            metadata=metadata or {},
            completed_at=completed_at,
        )
        if updated_job:
            self.job = updated_job
        return updated_job
