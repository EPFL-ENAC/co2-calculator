from abc import ABC, abstractmethod
from asyncio.log import logger
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db import SessionLocal
from app.models.data_ingestion import (
    DataIngestionJob,
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
        # add other params only if needed for provider logic
    ):
        self.config = config or {}
        self.user = user
        self.job_id: Optional[int] = None

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
        year: int,
        ingestion_method: IngestionMethod,
        target_type: TargetType,
        factor_type_id: FactorType | None = None,
    ) -> int:
        async with SessionLocal() as db:
            repo = DataIngestionRepository(db)
            job = await repo.create_ingestion_job(
                DataIngestionJob(
                    module_type_id=module_type_id,
                    year=year,
                    target_type=target_type,
                    ingestion_method=ingestion_method,
                    status=IngestionStatus.NOT_STARTED,
                    status_message="Job created",
                    meta={
                        "factor_type_id": factor_type_id if factor_type_id else None,
                    },
                    provider=self.user.provider if self.user else None,
                ),
            )
            if not job:
                raise Exception("Failed to create ingestion job")
            self.job_id = job.id
            if self.job_id is None:
                raise Exception("Failed to create ingestion job id")

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
            return {"status_code": 200, "message": "Success", "data": result}
        except Exception as e:
            await self._update_job(
                status_message="failed",
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
        async with SessionLocal() as db:
            repo = DataIngestionRepository(db)
            await repo.update_ingestion_job(
                job_id=self.job_id,
                status_message=status_message,
                status_code=status_code,
                metadata=metadata,
                completed_at=datetime.utcnow()
                if status_code in [IngestionStatus.COMPLETED, IngestionStatus.FAILED]
                else None,
            )
