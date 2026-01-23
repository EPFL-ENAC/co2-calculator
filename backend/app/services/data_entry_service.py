"""Headcount service for business logic."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.data_entry import DataEntry
from app.models.data_entry_type import DataEntryTypeEnum
from app.models.user import User

# from app.repositories.headcount_repo import HeadCountRepository
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.carbon_report_response import (
    ModuleResponse,
    ModuleTotals,
    SubmoduleResponse,
    SubmoduleSummary,
)
from app.schemas.data_entry import DataEntryCreate, DataEntryResponse, DataEntryUpdate

logger = get_logger(__name__)


class DataEntryService:
    """Service for data entry business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DataEntryRepository(session)

    async def get_module_stats(
        self, carbon_report_module_id: int, aggregate_by: str = "submodule"
    ) -> dict[str, float]:
        """Get module statistics such as total items and submodules."""
        # GOAL return total items and submodules for headcount module
        # data should be aggregated by aggregate_by param
        # {"professor": 10, "researcher": 5, ...}
        # or {"member": 15, "student": 20, ...}
        return await self.repo.get_module_stats(
            carbon_report_module_id=carbon_report_module_id, aggregate_by=aggregate_by
        )

    async def create(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: str,
        user: User,
        data: DataEntryCreate,
        # provider_source: str,
        # user_id: str,
    ) -> DataEntry:
        """Create a new headcount record."""
        # check if user.permissions allow creation

        logger.info(
            f"Creating data entry for module_id={sanitize(carbon_report_module_id)} "
            f"data_entry_type_id={sanitize(data_entry_type_id)} "
            f"user_id={sanitize(user.id)}"
        )
        entry = DataEntry(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=data_entry_type_id,
            data=data.model_dump(),
        )

        return await self.repo.create(entry)

    async def update(
        self,
        id: int,
        data: DataEntryUpdate,
        user: User,
    ) -> Optional[DataEntryResponse]:
        """Update an existing headcount record."""
        if not user or not user.id:
            logger.error("User context is required for updating data entry")
            raise PermissionError("User context is required for updating data entry")
        entry = await self.repo.update(
            id=id,
            data=data,
            user_id=user.id,
        )
        if entry is None:
            return None
        return DataEntryResponse.model_validate(entry)

    async def delete(self, id: int, current_user: User) -> bool:
        """Delete a headcount record."""
        if (
            current_user.has_role("co2.backoffice.admin") is False
            and current_user.has_role("co2.user.principal") is False
            and current_user.has_role("co2.user.secondary") is False
        ):
            logger.warning(
                f"Unauthorized delete attempt by user={sanitize(current_user.id)} "
                f"for data_entry_id={sanitize(id)}"
            )
            raise PermissionError("User not authorized to delete headcount records.")
        return await self.repo.delete(id)

    async def get(self, id: int) -> Optional[DataEntryResponse]:
        """Get headcount record by ID."""
        entry = await self.repo.get(id)
        if entry is None:
            return None
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
        """Get headcount record by carbon_report_module_id."""
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

        # total_annual_fte = sum(
        #     summary_by_submodule.get(k, {}).get("annual_fte", 0.0)
        #     for k in [
        #         DataEntryTypeEnum.member.value,
        #         DataEntryTypeEnum.student.value,
        #     ]
        # )
        # TBImplemented
        total_annual_fte = 0.0

        totals = ModuleTotals(
            total_annual_fte=round(total_annual_fte, 2),
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
        """Get headcount module data for a unit and year."""
        return await self.repo.get_submodule_data(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=data_entry_type_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )

    # async def get_by_workspace(self, unit_id: int, date: str) -> Optional[HeadCount]:
    #     """Get headcount record by unit_id and date."""
    #     return await self.repo.get_by_workspace(unit_id, date)
