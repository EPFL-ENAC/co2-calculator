"""Headcount service for business logic."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.data_entry_type import DataEntryTypeEnum
from app.models.data_ingestion import IngestionMethod
from app.models.headcount import HeadCount, HeadCountCreate, HeadCountUpdate
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.repositories.headcount_repo import HeadCountRepository
from app.schemas.carbon_report_response import (
    ModuleResponse,
    ModuleTotals,
    SubmoduleResponse,
    SubmoduleSummary,
)
from app.services.authorization_service import get_data_filters
from app.services.carbon_report_module_service import CarbonReportModuleService

logger = get_logger(__name__)


class HeadcountService:
    """Service for headcount business logic with context injection."""

    def __init__(self, session: AsyncSession, user: Optional[User] = None):
        self.session = session
        self.repo = HeadCountRepository(session)
        self.user = user

    async def get_module_stats(
        self, unit_id: int, year: int, aggregate_by: str = "submodule"
    ) -> dict[str, float]:
        """Get module statistics such as total items and submodules."""
        # GOAL return total items and submodules for headcount module
        # data should be aggregated by aggregate_by param
        # {"professor": 10, "researcher": 5, ...}
        # or {"member": 15, "student": 20, ...}
        return await self.repo.get_module_stats(
            unit_id=unit_id, year=year, aggregate_by=aggregate_by
        )

    async def create_headcount(
        self,
        data: HeadCountCreate,
        provider_source: IngestionMethod,
        user_id: int,
    ) -> HeadCount:
        """Create a new headcount record."""
        return await self.repo.create_headcount(
            data=data,
            provider_source=provider_source,
            user_id=user_id,
        )

    async def update_headcount(
        self,
        headcount_id: int,
        data: HeadCountUpdate,
        user: User,
    ) -> Optional[HeadCount]:
        """Update an existing headcount record."""
        if not user or not user.id:
            logger.error("User context is required for updating headcount")
            return None
        return await self.repo.update_headcount(
            headcount_id=headcount_id,
            data=data,
            user_id=user.id,
        )

    async def delete_headcount(self, headcount_id: int) -> bool:
        """Delete a headcount record.

        Authorization is handled at the API route level via require_permission().
        This method focuses purely on the business logic of deletion.

        Args:
            headcount_id: The ID of the headcount record to delete

        Returns:
            bool: True if deletion was successful
        """
        return await self.repo.delete_headcount(headcount_id)

    async def get_by_id(self, item_id: int) -> Optional[HeadCount]:
        """Get headcount record by ID with policy-based filtering."""
        headcount = await self.repo.get_by_id(item_id)

        # Apply policy-based access check if user context is available
        if self.user and headcount:
            from app.services.authorization_service import check_resource_access

            resource_dict = {
                "id": headcount.id,
                "created_by": headcount.created_by,
                "unit_id": headcount.unit_id,
            }

            if not await check_resource_access(self.user, "headcount", resource_dict):
                return None

        return headcount

    async def get_headcounts(
        self,
        unit_id: int,
        year: int,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "id",
        sort_order: str = "asc",
        filter: Optional[str] = None,
    ) -> list[HeadCount]:
        """Get headcount record by unit_id and year with policy-based filtering."""
        # Get policy-based filters if user context is available
        filters = None
        if self.user:
            filters = await get_data_filters(self.user, "headcount", "list")

        return await self.repo.get_headcounts(
            unit_id, year, limit, offset, sort_by, sort_order, filter, filters=filters
        )

    async def get_module_data(
        self,
        unit_id: int,
        year: int,
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
            f"Fetching module data for unit={sanitize(unit_id)}, "
            f"year={sanitize(year)}, "
            f"module=headcount"
        )

        # Get summary statistics by submodule
        summary_by_submodule = await self.repo.get_summary_by_submodule(
            unit_id=unit_id, year=year
        )

        submodules = {}
        submodule_keys = [
            DataEntryTypeEnum.member.value,
            DataEntryTypeEnum.student.value,
        ]
        # Process each submodule
        for submodule_key in submodule_keys:
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
            )

            submodules[submodule_key] = submodule_response

        # Calculate module totals using SQL summaries (not Python sums)
        total_submodules = len(submodules)
        # total_items = sum(
        #     summary_by_submodule.get(k, {}).get("total_items", 0)
        #     for k in [
        #         DataEntryTypeEnum.member.value,
        #         DataEntryTypeEnum.student.value,
        #     ]
        # )
        total_annual_fte = sum(
            summary_by_submodule.get(k, {}).get("annual_fte", 0.0)
            for k in [
                DataEntryTypeEnum.member.value,
                DataEntryTypeEnum.student.value,
            ]
        )

        totals = ModuleTotals(
            # total_submodules=total_submodules,
            # total_items=,
            total_annual_fte=round(total_annual_fte, 2),
            total_kg_co2eq=None,
            total_tonnes_co2eq=None,
            total_annual_consumption_kwh=None,
        )

        # find carbon_report_module_id from year/unit_id mapping:
        CarbonReportModuleService_instance = CarbonReportModuleService(self.session)
        carbon_report_module = (
            await CarbonReportModuleService_instance.get_carbon_report_by_year_and_unit(
                unit_id=unit_id,
                year=year,
                module_type_id=ModuleTypeEnum.headcount.value,
            )
        )
        # Create module response
        module_response = ModuleResponse(
            carbon_report_module_id=carbon_report_module.id
            if carbon_report_module
            else None,
            stats=None,
            retrieved_at=datetime.now(timezone.utc),
            submodules=submodules,
            data_entry_types_total_items={k: 0 for k in submodules.keys()},
            totals=totals,
        )

        return module_response

    async def get_submodule_data(
        self,
        unit_id: int,
        year: int,
        submodule_key: str,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "date",
        sort_order: str = "asc",
        filter: Optional[str] = None,
    ) -> SubmoduleResponse:
        """Get headcount module data for a unit and year."""
        return await self.repo.get_submodule_data(
            unit_id=unit_id,
            year=year,
            submodule_key=submodule_key,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )

    async def get_by_unit_and_date(
        self, unit_id: int, date: str
    ) -> Optional[HeadCount]:
        """Get headcount record by unit_id and date."""
        return await self.repo.get_by_unit_and_date(unit_id, date)
