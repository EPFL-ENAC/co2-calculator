"""Simulator plan service for business logic.

A "plan" (project planner project) is a ``CarbonProject`` row with
``carbon_report_type = SIMULATOR_PLAN``; its ``name`` is the URL identifier
shown in the project planner routes.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReportType
from app.models.user import User
from app.repositories.carbon_project_repo import CarbonProjectRepository
from app.schemas.simulator_plan import SimulatorPlanRead
from app.services.carbon_report_service import CarbonReportService

logger = get_logger(__name__)

DEFAULT_PLAN_NAME = "new-project"


def _next_available_name(base: str, existing: set[str]) -> str:
    """Return ``base`` if free, else the first free ``base-2``, ``base-3``, ..."""
    if base not in existing:
        return base
    return _next_suffixed_name(base, existing)


def _next_suffixed_name(base: str, existing: set[str]) -> str:
    """Return the first free ``base-2``, ``base-3``, ... (never bare ``base``)."""
    counter = 2
    while f"{base}-{counter}" in existing:
        counter += 1
    return f"{base}-{counter}"


def _to_read(project: CarbonProject, creator_name: Optional[str]) -> SimulatorPlanRead:
    if project.id is None:
        raise ValueError("project must be persisted before use")
    return SimulatorPlanRead(
        id=project.id,
        unit_id=project.unit_id,
        name=project.name or "",
        created_by=project.created_by,
        created_at=project.created_at,
        creator_name=creator_name,
    )


class SimulatorPlanService:
    """Service for simulator plan (project planner) business logic.

    Flushes within the session; committing is the caller's (route's)
    responsibility, matching :class:`CarbonReportService`.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CarbonProjectRepository(session)
        self.report_service = CarbonReportService(session)

    async def list_plans(self, unit_id: int) -> list[SimulatorPlanRead]:
        """List all plans for a unit, newest first."""
        rows = await self.repo.list_plans_by_unit(unit_id)
        return [_to_read(project, creator_name) for project, creator_name in rows]

    async def get_plan_by_name(
        self, unit_id: int, name: str
    ) -> Optional[SimulatorPlanRead]:
        """Get a plan by unit and name, or None."""
        row = await self.repo.get_plan_by_name(unit_id, name)
        if row is None:
            return None
        project, creator_name = row
        return _to_read(project, creator_name)

    async def create_plan(
        self, *, unit_id: int, user: User, name: Optional[str] = None
    ) -> SimulatorPlanRead:
        """Create a plan for a unit, owned by ``user``.

        Without an explicit ``name``, assigns the next available default name
        (new-project, new-project-2, ...). An explicit name that collides with
        an existing plan of the unit raises ``ValueError``.
        """
        existing_names = await self.repo.list_plan_names(unit_id)
        if name is None:
            name = _next_available_name(DEFAULT_PLAN_NAME, existing_names)
        elif name in existing_names:
            raise ValueError(f"A plan named '{name}' already exists for this unit")
        project = CarbonProject(
            unit_id=unit_id,
            carbon_report_type=CarbonReportType.SIMULATOR_PLAN,
            name=name,
            created_by=user.id,
            created_at=datetime.now(timezone.utc),
        )
        project = await self._flush_guarded(self.repo.create(project))
        return _to_read(project, user.display_name)

    async def rename_plan(
        self, plan_id: int, new_name: str
    ) -> Optional[SimulatorPlanRead]:
        """Rename a plan; returns None if the plan does not exist.

        Renaming to the current name is a no-op; a collision with another
        plan of the same unit raises ``ValueError``.
        """
        project = await self.repo.get_plan(plan_id)
        if project is None:
            return None
        if new_name != project.name:
            existing_names = await self.repo.list_plan_names(project.unit_id)
            if new_name in existing_names:
                raise ValueError(
                    f"A plan named '{new_name}' already exists for this unit"
                )
            project.name = new_name
            project = await self._flush_guarded(self.repo.create(project))
        return await self._read_with_creator(project)

    async def duplicate_plan(
        self, plan_id: int, user: User
    ) -> Optional[SimulatorPlanRead]:
        """Duplicate a plan as ``<name>-2`` (then ``-3``, ...); None if missing.

        Only the project row is copied for now; plan contents (carbon reports)
        will need copying once the planner page stores data.
        """
        source = await self.repo.get_plan(plan_id)
        if source is None:
            return None
        existing_names = await self.repo.list_plan_names(source.unit_id)
        new_name = _next_suffixed_name(source.name or "", existing_names)
        copy = CarbonProject(
            unit_id=source.unit_id,
            carbon_report_type=CarbonReportType.SIMULATOR_PLAN,
            start_year=source.start_year,
            end_year=source.end_year,
            name=new_name,
            is_viewable_by_unit_members=source.is_viewable_by_unit_members,
            created_by=user.id,
            created_at=datetime.now(timezone.utc),
        )
        copy = await self._flush_guarded(self.repo.create(copy))
        return _to_read(copy, user.display_name)

    async def delete_plan(self, plan_id: int) -> bool:
        """Delete a plan and any carbon reports attached to it.

        ``carbon_reports.carbon_project_id`` has no ON DELETE cascade, so
        dependent reports (and their modules) are deleted explicitly first.
        """
        project = await self.repo.get_plan(plan_id)
        if project is None:
            return False
        report_ids = await self.repo.list_report_ids_for_project(plan_id)
        for report_id in report_ids:
            await self.report_service.delete(report_id)
        await self.repo.delete(project)
        return True

    async def _read_with_creator(self, project: CarbonProject) -> SimulatorPlanRead:
        """Build a Read DTO resolving the creator display name via the join."""
        row = await self.repo.get_plan_by_name(project.unit_id, project.name or "")
        if row is None:
            return _to_read(project, None)
        refreshed, creator_name = row
        return _to_read(refreshed, creator_name)

    @staticmethod
    async def _flush_guarded(awaitable) -> CarbonProject:
        """Await a repo write, mapping unique-index races to ValueError."""
        try:
            return await awaitable
        except IntegrityError as exc:
            raise ValueError(
                "A plan with this name already exists for this unit"
            ) from exc
