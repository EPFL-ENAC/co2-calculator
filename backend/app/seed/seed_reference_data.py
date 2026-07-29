"""Seed reference data (airports, train stations, building rooms) from CSV.

Reference data is year-agnostic global state: the rows land in ``locations``
and ``building_rooms``, which carry no year column.  The seed reuses
``ReferenceDataCSVProvider`` — the exact provider the backoffice
"reference data" upload runs — reading from local disk instead of the file
store, so seeded rows are indistinguishable from uploaded ones.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import IngestionResult, IngestionState, TargetType
from app.models.module_type import ModuleTypeEnum
from app.seed._stub_jobs import create_seed_stub_job
from app.services.data_ingestion.csv_providers.reference_data import (
    ReferenceDataCSVProvider,
)

logger = get_logger(__name__)

INPUT_DATA_FOLDER = Path(__file__).parent.parent.parent / "INPUT_DATA"
DEFAULT_YEAR = 2025


@dataclass
class ReferenceSeedConfig:
    """One reference CSV and the (module, data-entry) pair it belongs to."""

    path: Path
    data_entry_type: DataEntryTypeEnum
    module_type: ModuleTypeEnum


REFERENCE_SEEDS: list[ReferenceSeedConfig] = [
    ReferenceSeedConfig(
        path=INPUT_DATA_FOLDER / "travel_planes_reference.csv",
        data_entry_type=DataEntryTypeEnum.plane,
        module_type=ModuleTypeEnum.professional_travel,
    ),
    ReferenceSeedConfig(
        path=INPUT_DATA_FOLDER / "travel_trains_reference.csv",
        data_entry_type=DataEntryTypeEnum.train,
        module_type=ModuleTypeEnum.professional_travel,
    ),
    ReferenceSeedConfig(
        path=INPUT_DATA_FOLDER / "building_rooms_reference.csv",
        data_entry_type=DataEntryTypeEnum.building,
        module_type=ModuleTypeEnum.buildings,
    ),
]


class LocalReferenceCSVProvider(ReferenceDataCSVProvider):
    """Reference CSV provider that reads from local disk.

    Mirrors ``LocalFactorCSVProvider`` (``csv_providers/local_seed.py``):
    no ``DataIngestionJob`` row, no file-store staging.  Header validation,
    the locations COPY + natural-key UPSERT and the building-rooms
    delete-and-insert are all inherited untouched.

    Config keys
    -----------
    local_file_path : str
        Absolute path to the CSV file on disk.
    data_entry_type_id : int
        plane (20), train (21) or building (30) — the base class dispatches
        on this.
    """

    def __init__(self, config: Dict[str, Any], data_session: AsyncSession):
        super().__init__(
            config=config,
            user=None,
            job_session=None,
            data_session=data_session,
        )
        self._local_file_path = Path(config["local_file_path"])

    async def validate_connection(self) -> bool:
        exists = self._local_file_path.is_file()
        if not exists:
            logger.warning(f"Local CSV file not found: {self._local_file_path}")
        return exists

    async def _stage_file(self) -> tuple[str, str, str]:
        """Read the CSV off disk instead of moving it through the file store."""
        if not self._local_file_path.is_file():
            raise FileNotFoundError(f"CSV file not found: {self._local_file_path}")
        # utf-8-sig so a BOM-prefixed export does not poison the first header.
        csv_text = self._local_file_path.read_text(encoding="utf-8-sig")
        return csv_text, str(self._local_file_path), self._local_file_path.name

    async def _move_to_processed(self, processing_path: str) -> str:
        # Seed CSVs live in the repo, not the file store — nothing to archive.
        return processing_path

    async def _update_job(
        self,
        status_message: str,
        extra_metadata: dict | None = None,
        state: Optional[IngestionState] = None,
        result: Optional[IngestionResult] = None,
    ) -> None:
        # Local seed runs do not persist ingestion jobs.
        logger.debug(
            "LocalReferenceCSVProvider state=%s, message=%s", state, status_message
        )
        return None


async def seed_reference_data_file(
    session: AsyncSession,
    config: ReferenceSeedConfig,
    year: int = DEFAULT_YEAR,
) -> None:
    """Ingest one reference CSV and plant the matching data-management stub job."""
    if not config.path.is_file():
        raise FileNotFoundError(f"Reference CSV not found: {config.path}")

    provider = LocalReferenceCSVProvider(
        config={
            "local_file_path": str(config.path),
            "module_type_id": config.module_type.value,
            "data_entry_type_id": config.data_entry_type.value,
            "year": year,
        },
        data_session=session,
    )
    result = await provider.ingest()

    data = result.get("data", {})
    inserted = data.get("inserted", 0)
    skipped = data.get("skipped", 0)
    print(
        f"Ingested {inserted} {config.data_entry_type.name} reference rows "
        f"({skipped} skipped)"
    )

    # Same rationale as the factor seed: without a stub job the rows exist in
    # the DB but the backoffice data-management card stays blank.
    await create_seed_stub_job(
        session,
        module_type_id=config.module_type.value,
        data_entry_type_id=config.data_entry_type.value,
        year=year,
        target_type=TargetType.REFERENCE_DATA,
        job_type="reference_ingest",
        file_path=config.path,
        rows_processed=inserted,
        rows_skipped=skipped,
    )

    await session.commit()
    logger.info(f"Seeded {config.data_entry_type.name} reference data.")


async def seed_all_reference_data(
    session: AsyncSession, year: int = DEFAULT_YEAR
) -> None:
    """Ingest every CSV in ``REFERENCE_SEEDS``."""
    for config in REFERENCE_SEEDS:
        await seed_reference_data_file(session, config, year)


async def main(year: int = DEFAULT_YEAR) -> None:
    async with SessionLocal() as session:
        await seed_all_reference_data(session, year)


if __name__ == "__main__":
    asyncio.run(main())
