"""Headcount service for business logic."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.headcount import HeadCount, HeadCountCreate, HeadCountUpdate
from app.models.user import User
from app.repositories.headcount_repo import HeadCountRepository
from app.schemas.equipment import (
    ModuleResponse,
    ModuleTotals,
    SubmoduleResponse,
    SubmoduleSummary,
)

logger = get_logger(__name__)


class HeadcountService:
    """Service for headcount business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = HeadCountRepository(session)

    async def get_module_stats(
        self, unit_id: str, year: int, aggregate_by: str = "submodule"
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
        provider_source: str,
        user_id: str,
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
        return await self.repo.update_headcount(
            headcount_id=headcount_id,
            data=data,
            user_id=user.id,
        )

    async def delete_headcount(self, headcount_id: int, current_user: User) -> bool:
        """Delete a headcount record."""
        if (
            current_user.has_role("co2.backoffice.admin") is False
            and current_user.has_role("co2.user.principal") is False
            and current_user.has_role("co2.user.secondary") is False
        ):
            logger.warning(
                f"Unauthorized delete attempt by user={sanitize(current_user.id)} "
                f"for headcount_id={sanitize(headcount_id)}"
            )
            raise PermissionError("User not authorized to delete headcount records.")
        return await self.repo.delete_headcount(headcount_id)

    async def get_by_id(self, item_id: int) -> Optional[HeadCount]:
        """Get headcount record by ID."""
        return await self.repo.get_by_id(item_id)

    async def get_headcounts(
        self,
        unit_id: str,
        year: int,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "id",
        sort_order: str = "asc",
        filter: Optional[str] = None,
    ) -> list[HeadCount]:
        """Get headcount record by unit_id and year."""
        return await self.repo.get_headcounts(
            unit_id, year, limit, offset, sort_by, sort_order, filter
        )

    async def get_module_data(
        self,
        unit_id: str,
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
            total_annual_consumption_kwh=None,
        )

        # Create module response
        module_response = ModuleResponse(
            module_type="my-lab",
            unit=unit_id,
            year=year,
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
        unit_id: str,
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
        self, unit_id: str, date: str
    ) -> Optional[HeadCount]:
        """Get headcount record by unit_id and date."""
        return await self.repo.get_by_unit_and_date(unit_id, date)
