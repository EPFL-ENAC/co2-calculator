"""DataEntry service for business logic."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.user import User

# from app.repositories.headcount_repo import HeadCountRepository
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.carbon_report_response import (
    ModuleResponse,
    ModuleTotals,
    SubmoduleResponse,
)
from app.schemas.data_entry import DataEntryCreate, DataEntryResponse, DataEntryUpdate

logger = get_logger(__name__)


class DataEntryService:
    """Service for data entry business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DataEntryRepository(session)

    async def get_stats(
        self,
        carbon_report_module_id: int,
        aggregate_by: str = "data_entry_type_id",
        aggregate_field: str = "fte",
    ) -> dict[str, float]:
        """Get module statistics such as total items and submodules."""
        return await self.repo.get_stats(
            carbon_report_module_id=carbon_report_module_id,
            aggregate_by=aggregate_by,
            aggregate_field=aggregate_field,
        )

    async def get_stats_by_carbon_report_id(
        self,
        carbon_report_id: int,
        aggregate_by: str = "data_entry_type_id",
        aggregate_field: str = "fte",
    ) -> dict[str, float]:
        """Get validated DataEntry totals across modules for a carbon report."""
        return await self.repo.get_stats_by_carbon_report_id(
            carbon_report_id=carbon_report_id,
            aggregate_by=aggregate_by,
            aggregate_field=aggregate_field,
        )

    async def create(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: int,
        user: User,
        data: DataEntryCreate,
    ) -> DataEntryResponse:
        logger.info(
            f"Creating data entry for module_id={sanitize(carbon_report_module_id)} "
            f"data_entry_type_id={sanitize(data_entry_type_id)} "
            f"user_id={sanitize(user.id)}"
        )
        entry = DataEntry(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=data_entry_type_id,
            data=data.data,
        )

        created_entry = await self.repo.create(entry)

        # 3. replace by flush; commit should happen in 'orchestrator' or 'route'
        # top level domain)
        await self.session.flush()
        await self.session.refresh(created_entry)

        # 5. return response
        return DataEntryResponse.model_validate(created_entry)

    async def bulk_create(
        self, data_entries: list[DataEntry]
    ) -> list[DataEntryResponse]:
        """Bulk create data entries."""
        logger.info(f"Bulk creating {len(data_entries)} data entries")
        db_objs = await self.repo.bulk_create(data_entries)
        # await self.session.flush()  # Ensure data_entry IDs are populated
        return [DataEntryResponse.model_validate(obj) for obj in db_objs]

    async def bulk_delete(
        self, carbon_report_module_id: int, data_entry_type_id: DataEntryTypeEnum
    ) -> None:
        """Bulk delete data entries by module and type."""
        logger.info(
            f"Bulk deleting data entries\n"
            f"for module_id={sanitize(carbon_report_module_id)}\n"
            f"data_entry_type_id={sanitize(data_entry_type_id.value)}"
        )
        await self.repo.bulk_delete(carbon_report_module_id, data_entry_type_id)
        await self.session.flush()

    async def update(
        self,
        id: int,
        data: DataEntryUpdate,
        user: User,
    ) -> DataEntryResponse:
        """Update an existing record."""
        if not user or not user.id:
            logger.error("User context is required for updating data entry")
            raise PermissionError("User context is required for updating data entry")
        entry = await self.repo.update(
            id=id,
            data=data,
            user_id=user.id,
        )
        if entry is None:
            raise ValueError(f"Data entry with id={id} not found")
        await self.session.refresh(entry)
        return DataEntryResponse.model_validate(entry)

    async def delete(self, id: int, current_user: User) -> bool:
        """Delete a record."""
        result = await self.repo.delete(id)
        await self.session.flush()

        if result is False:
            raise ValueError(f"Data entry with id={id} not found")
        return True

    async def get(self, id: int) -> DataEntryResponse:
        """Get record by ID."""
        entry = await self.repo.get(id)
        if entry is None:
            raise ValueError(f"Data entry with id={id} not found")
        return DataEntryResponse.model_validate(entry)

    async def get_list(
        self,
        carbon_report_module_id: int,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "id",
        sort_order: str = "asc",
        filter: Optional[str] = None,
    ) -> list[DataEntryResponse]:
        """Get  record by carbon_report_module_id."""
        entries = await self.repo.get_list(
            carbon_report_module_id, limit, offset, sort_by, sort_order, filter
        )
        return [DataEntryResponse.model_validate(entry) for entry in entries]

    async def get_module_data(
        self,
        carbon_report_module_id: int,
    ) -> ModuleResponse:
        data_entry_types_total_items = await self.repo.get_total_count_by_submodule(
            carbon_report_module_id=carbon_report_module_id
        )
        # more info in routes carbon_report_module (cf DataEntryEmissionService)
        # we just return empty stats and totals, it's computed in routes
        totals = ModuleTotals(
            total_annual_fte=None,
            total_kg_co2eq=None,
            total_tonnes_co2eq=None,
            total_annual_consumption_kwh=None,
        )

        # Create module response
        module_response = ModuleResponse(
            carbon_report_module_id=carbon_report_module_id,
            retrieved_at=datetime.now(timezone.utc),
            data_entry_types_total_items=data_entry_types_total_items,
            stats=None,
            totals=totals,
        )
        return module_response

    async def get_submodule_data(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: int,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "date",
        sort_order: str = "asc",
        filter: Optional[str] = None,
    ) -> SubmoduleResponse:
        """Get module data for a unit and year."""
        return await self.repo.get_submodule_data(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=data_entry_type_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )

    async def get_total_per_field(
        self,
        field_name: str,
        carbon_report_module_id: int,
        data_entry_type_id: Optional[int],
    ) -> Optional[float]:
        """Get total sum of a specific field for a given module and data entry type."""
        return await self.repo.get_total_per_field(
            field_name=field_name,
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=data_entry_type_id,
        )
