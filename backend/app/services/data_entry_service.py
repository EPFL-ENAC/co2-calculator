"""Headcount service for business logic."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.data_entry import DataEntry
from app.models.user import User

# from app.repositories.headcount_repo import HeadCountRepository
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.data_entry import DataEntryCreate, DataEntryResponse, DataEntryUpdate
from app.schemas.equipment import (
    ModuleResponse,
    ModuleTotals,
    SubmoduleResponse,
    SubmoduleSummary,
)

# from app.schemas.headcount import HeadCountCreate, HeadCountUpdate

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

    # carbon_report_module_id=carbon_report_module_id,
    #         data_entry_type_id=data_entry_type_id,
    #         user=current_user,
    #         data=item_data,

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
    ) -> Optional[DataEntry]:
        """Update an existing headcount record."""
        return await self.repo.update(
            id=id,
            data=data,
            user_id=user.id,
        )

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

    async def get_by_id(self, id: int) -> Optional[DataEntryResponse]:
        """Get headcount record by ID."""
        return await self.repo.get_by_id(id)

    async def get_list(
        self,
        unit_id: int,
        year: int,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "id",
        sort_order: str = "asc",
        filter: Optional[str] = None,
    ) -> list[DataEntryResponse]:
        """Get headcount record by unit_id and year."""
        return await self.repo.get_headcounts(
            unit_id, year, limit, offset, sort_by, sort_order, filter
        )

    async def get_module_data(
        self,
        carbon_report_module_id: int,
    ) -> ModuleResponse:
        """
        Get complete module data with all submodules.

        Args:
            session: Database session
            unit_id: Unit ID to filter equipment
            year: Year for the data (currently informational only)
            preview_limit: Optional limit for items per submodule

        Returns:
            ModuleResponse with all submodules and their equipment
        """
        logger.info(
            f"Fetching module data for module_id={sanitize(carbon_report_module_id)}, "
            f"module=headcount"
        )

        # Get summary statistics by submodule
        summary_by_submodule = await self.repo.get_summary_by_submodule(
            carbon_report_module_id=carbon_report_module_id
        )

        submodules = {}

        # Process each submodule
        for submodule_key in ["member", "student"]:
            # Get summary for this submodule
            submodule_summary_data = summary_by_submodule.get(
                submodule_key,
                {"total_items": 0, "annual_fte": 0.0},
            )

            summary = SubmoduleSummary(**submodule_summary_data)
            total_count = submodule_summary_data["total_items"]

            # Create submodule response
            submodule_response = SubmoduleResponse(
                id=submodule_key,
                count=total_count,
                summary=summary,
                items=[],  # Detailed items can be fetched separately
                has_more=False,
                name="DEPRECATED field",
            )

            submodules[submodule_key] = submodule_response

        # Calculate module totals using SQL summaries (not Python sums)
        total_submodules = len(submodules)
        total_items = sum(
            summary_by_submodule.get(k, {}).get("total_items", 0)
            for k in ["member", "student"]
        )
        total_annual_fte = sum(
            summary_by_submodule.get(k, {}).get("annual_fte", 0.0)
            for k in ["member", "student"]
        )

        totals = ModuleTotals(
            total_submodules=total_submodules,
            total_items=total_items,
            total_annual_fte=round(total_annual_fte, 2),
            total_kg_co2eq=None,
            total_tonnes_co2eq=None,
            total_annual_consumption_kwh=None,
        )

        # Create module response
        module_response = ModuleResponse(
            module_type="my-lab",
            carbon_report_module_id=carbon_report_module_id,
            stats=None,
            retrieved_at=datetime.now(timezone.utc),
            submodules=submodules,
            totals=totals,
        )

        logger.info(
            f"Module data retrieved: {sanitize(total_items)} items across "
            f"{sanitize(total_submodules)} submodules"
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
