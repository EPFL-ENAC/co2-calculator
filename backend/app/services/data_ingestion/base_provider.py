from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    FactorType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.repositories.data_ingestion import DataIngestionRepository

logger = get_logger(__name__)


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
        # Plan 310-C: when the runner drives dispatch, it owns the
        # FINISHED transition (so finished_at, the preempt-check, and
        # factor_ingest's chain-job fan-out all happen in the right
        # order).  Callers running providers via ``run_job`` set this
        # to True after construction; it gates the FINISHED state-write
        # in ``_update_job`` (status_message + extra_metadata still
        # flow through for SSE progress).
        self.defer_finalize: bool = False

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
        ingestion_method: IngestionMethod,
        entity_type: EntityType,
        target_type: TargetType,
        module_type_id: Optional[ModuleTypeEnum] = None,
        data_entry_type_id: Optional[int] = None,
        year: Optional[int] = None,
        factor_type_id: FactorType | None = None,
        config: Dict[str, Any] | None = None,
        db: AsyncSession | None = None,
        request_context: dict | None = None,
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
        if self.user is None or self.user.provider is None:
            raise ValueError("User provider is required to create ingestion job")
        meta = {
            "factor_type_id": factor_type_id.value if factor_type_id else None,
            "config": job_config,  # Store entire config in meta for job
            # Creator identity for the pipeline-console "author" column.
            # Stored on the job so the list endpoint resolves the author
            # without a users-table join (the User is guaranteed above).
            "created_by": {
                "user_id": self.user.id,
                "email": self.user.email,
                "name": self.user.display_name,
            },
        }
        data = DataIngestionJob(
            module_type_id=module_type_id,
            ingestion_method=ingestion_method,
            data_entry_type_id=data_entry_type_id,
            entity_type=entity_type,
            target_type=target_type,
            state=IngestionState.NOT_STARTED,
            result=None,
            status_message="Job created",
            meta=meta,
            provider=self.user.provider,
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
        handler_id = self.user.institutional_id if self.user else "csv_ingestion"

        await audit_service.create_version(
            entity_type="DataIngestionJob",
            entity_id=self.job_id,
            data_snapshot=job.model_dump(),
            change_type=AuditChangeTypeEnum.CREATE,
            changed_by=changed_by,
            change_reason=f"Data ingestion job created via {ingestion_method.value}",
            handler_id=handler_id,
            handled_ids=[],  # No specific handled IDs for job creation
            ip_address=request_context.get("ip_address") if request_context else None,
            route_path=request_context.get("route_path") if request_context else None,
            route_payload=request_context.get("route_payload")
            if request_context
            else None,
        )

        return self.job_id

    async def ingest(
        self,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        try:
            await self._update_job(
                status_message="processing",
                state=IngestionState.RUNNING,
                result=None,
                extra_metadata={"message": "Starting sync..."},
            )
            raw_data = await self.fetch_data(filters or {})
            await self._update_job(
                status_message="processing",
                state=IngestionState.RUNNING,
                result=None,
                extra_metadata={"message": f"Fetched {len(raw_data)} records"},
            )
            transformed_data = await self.transform_data(raw_data)
            await self._update_job(
                status_message="processing",
                state=IngestionState.RUNNING,
                result=None,
                extra_metadata={"message": "Transforming data..."},
            )
            result = await self._load_data(transformed_data)
            await self._update_job(
                status_message="completed",
                state=IngestionState.FINISHED,
                result=IngestionResult.SUCCESS,
                extra_metadata={
                    "message": f"Successfully processed {result['inserted']} records"
                },
            )
            return {
                "state": IngestionState.FINISHED,
                "status_message": "Success",
                "data": result,
            }
        except Exception as e:
            await self._update_job(
                status_message=f"failed: {str(e)}",
                state=IngestionState.FINISHED,
                result=IngestionResult.ERROR,
                extra_metadata={"error": str(e)},
            )
            logger.error(f"Ingestion failed: {str(e)}")
            raise

    async def _update_job(
        self,
        status_message: str,
        extra_metadata: dict | None = None,
        state: Optional[IngestionState] = None,
        result: Optional[IngestionResult] = None,
    ):
        # Only store essential config fields to avoid recursive nesting
        # (self.config may contain snapshots of previous meta, causing
        # meta.config.meta.config...)
        essential_config = {
            "module_type_id": self.config.get("module_type_id"),
            "year": self.config.get("year"),
            "target_type": self.config.get("target_type"),
            "ingestion_method": self.config.get("ingestion_method"),
            "data_entry_type_id": self.config.get("data_entry_type_id"),
            "carbon_report_module_id": self.config.get("carbon_report_module_id"),
            "entity_type": self.config.get("entity_type"),
            "file_path": self.config.get("file_path"),
        }
        # Remove None values
        essential_config = {k: v for k, v in essential_config.items() if v is not None}

        metadata = {"config": essential_config}
        if extra_metadata:
            metadata.update(extra_metadata)
        if not self.job_id:
            logger.warning("Job ID is not set. Cannot update ingestion job.")
            return
        if not self.job_session:
            logger.warning("No job session available. Cannot update ingestion job.")
            return

        # Plan 310-C: when the runner owns the FINISHED transition,
        # strip state + result from the write (and skip completed_at
        # stamping, which is auto-stamped on the runner's authoritative
        # FINISHED transition via PR #1026).  The status_message and
        # extra_metadata still land so SSE consumers see the
        # provider's final progress message; the row stays in RUNNING
        # until the runner's next call.
        write_state = state
        write_result = result
        write_completed_at: datetime | None = (
            datetime.now(timezone.utc) if state in (IngestionState.FINISHED,) else None
        )
        if self.defer_finalize and state == IngestionState.FINISHED:
            write_state = None
            write_result = None
            write_completed_at = None

        repo = DataIngestionRepository(self.job_session)
        await repo.update_ingestion_job(
            job_id=self.job_id,
            status_message=status_message,
            metadata=metadata,
            completed_at=write_completed_at,
            state=write_state,
            result=write_result,
        )

        # Mark as current if job is finished — only when we actually
        # wrote the FINISHED state, not when the runner deferred it.
        if (
            write_state in (IngestionState.FINISHED, IngestionState.RUNNING)
            and self.job_id
        ):
            job = await repo.get_job_by_id(self.job_id)
            if job:
                await repo.mark_job_as_current(job)

        # Commit immediately so SSE endpoints can see the update
        await self.job_session.commit()

    async def _update_job_and_sync(
        self,
        repo: DataIngestionRepository,
        job_id: int,
        status_message: str,
        metadata: dict | None = None,
        completed_at: datetime | None = None,
        state: Optional[IngestionState] = None,
        result: Optional[IngestionResult] = None,
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
            metadata=metadata or {},
            completed_at=completed_at,
            state=state,
            result=result,
        )
        if updated_job:
            self.job = updated_job
        return updated_job
