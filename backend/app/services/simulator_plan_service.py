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
from app.models.carbon_report import CarbonReport, CarbonReportType
from app.models.data_entry import DataEntry, DataEntrySourceEnum
from app.models.module_type import (
    MODULE_TYPE_TO_DATA_ENTRY_TYPES,
    PLANNER_PREFILLED_MODULE_TYPES,
    ModuleTypeEnum,
)
from app.models.user import User
from app.repositories.carbon_project_repo import CarbonProjectRepository
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.carbon_report import CarbonReportCreate, CarbonReportRead
from app.schemas.data_entry import DataEntryResponse
from app.schemas.simulator_plan import (
    SimulatorPlanRead,
    SimulatorPlanUpdate,
    SimulatorPlanYearRead,
)
from app.services.carbon_report_service import CarbonReportService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.utils.report_stats import merge_report_stats

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


def _to_read(
    project: CarbonProject,
    creator_name: Optional[str],
    total_tonnes_co2eq: Optional[float] = None,
) -> SimulatorPlanRead:
    if project.id is None:
        raise ValueError("project must be persisted before use")
    return SimulatorPlanRead(
        id=project.id,
        unit_id=project.unit_id,
        name=project.name or "",
        start_year=project.start_year,
        end_year=project.end_year,
        is_viewable_by_unit_members=project.is_viewable_by_unit_members,
        created_by=project.created_by,
        created_at=project.created_at,
        creator_name=creator_name,
        total_tonnes_co2eq=total_tonnes_co2eq,
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
        """List all plans for a unit, newest first, each with its total."""
        rows = await self.repo.list_plans_by_unit(unit_id)
        totals = await self._totals_by_plan(
            [project.id for project, _ in rows if project.id is not None]
        )
        return [
            _to_read(project, creator_name, totals.get(project.id or -1))
            for project, creator_name in rows
        ]

    async def _totals_by_plan(self, plan_ids: list[int]) -> dict[int, float]:
        """Sum each plan's year reports into tonnes CO2-eq, in one query.

        Goes through ``merge_report_stats`` — the same aggregation the plan
        page's ``/aggregate-stats`` headline uses — so the table and the plan
        cannot drift. Inactive modules are already excluded upstream by the
        report rollup.
        """
        by_plan: dict[int, list[dict]] = {plan_id: [] for plan_id in plan_ids}
        for plan_id, stats in await self.repo.list_report_stats_by_project(plan_ids):
            by_plan[plan_id].append(dict(stats or {}))
        return {
            plan_id: merge_report_stats(stats_list)["total"] / 1000.0
            for plan_id, stats_list in by_plan.items()
        }

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

    async def update_plan(
        self, plan_id: int, update: SimulatorPlanUpdate
    ) -> Optional[SimulatorPlanRead]:
        """Apply a PATCH to a plan; returns None if the plan does not exist.

        Renaming to the current name is a no-op; a collision with another
        plan of the same unit raises ``ValueError``. When the plan ends up
        with a complete year range, its per-year reports are synced to it.
        """
        project = await self.repo.get_plan(plan_id)
        if project is None:
            return None
        if update.name is not None and update.name != project.name:
            existing_names = await self.repo.list_plan_names(project.unit_id)
            if update.name in existing_names:
                raise ValueError(
                    f"A plan named '{update.name}' already exists for this unit"
                )
            project.name = update.name
        if update.is_viewable_by_unit_members is not None:
            project.is_viewable_by_unit_members = update.is_viewable_by_unit_members
        if update.start_year is not None:
            project.start_year = update.start_year
        if update.end_year is not None:
            project.end_year = update.end_year
        if (
            project.start_year is not None
            and project.end_year is not None
            and project.start_year > project.end_year
        ):
            raise ValueError("start_year must be <= end_year")
        project = await self._flush_guarded(self.repo.create(project))
        await self._sync_year_reports(project)
        return await self._read_with_creator(project)

    async def _sync_year_reports(self, project: CarbonProject) -> None:
        """Make the plan's reports match ``start_year..end_year``, one per year.

        Out-of-range reports are deleted together with their entries
        (destructive by design — the user shrank the range deliberately).
        No-op until both bounds are set.
        """
        if project.start_year is None or project.end_year is None:
            return
        if project.id is None:
            raise ValueError("project must be persisted before use")
        target_years = set(range(project.start_year, project.end_year + 1))
        existing_years: set[int] = set()
        for report in await self.repo.list_reports_for_project(project.id):
            if report.year in target_years:
                existing_years.add(report.year)
            elif report.id is not None:
                await self.report_service.delete(report.id)
        for year in sorted(target_years - existing_years):
            await self.report_service.create(
                CarbonReportCreate(
                    unit_id=project.unit_id,
                    year=year,
                    carbon_project_id=project.id,
                )
            )

    async def list_plan_years(
        self, plan_id: int
    ) -> Optional[list[SimulatorPlanYearRead]]:
        """List the plan's per-year reports with their modules, by year.

        Returns None when the plan does not exist (vs. [] for a plan whose
        year range is not set yet).
        """
        project = await self.repo.get_plan(plan_id)
        if project is None:
            return None
        if project.id is None:
            raise ValueError("project must be persisted before use")
        years: list[SimulatorPlanYearRead] = []
        for report in await self.repo.list_reports_for_project(project.id):
            years.append(await self._year_read(report))
        return years

    async def set_reference_year(
        self, plan_id: int, year: int, reference_year: int
    ) -> Optional[SimulatorPlanYearRead]:
        """Set the baseline year of one plan-year report; None if missing.

        Existing entries of the report get their emissions recomputed, since
        factor lookup follows the reference year.
        """
        reports = await self.repo.list_reports_for_project(plan_id)
        report = next((r for r in reports if r.year == year), None)
        if report is None:
            return None
        if report.reference_year != reference_year:
            report.reference_year = reference_year
            self.session.add(report)
            await self.session.flush()
            await self._prefill_reference_modules(report)
            await self._recalculate_report_emissions(report)
        return await self._year_read(report)

    async def _prefill_reference_modules(self, report: CarbonReport) -> None:
        """Auto-prefill every prefilled-behavior module from the reference year.

        Runs on reference-year set/change (there is no manual prefill trigger):
        each prefilled module gets its PLANNER_SNAPSHOT rows wiped and re-copied
        at 100% from the reference year's Calculator data; user-added rows
        survive. No-op when the reference year has no Calculator report for the
        unit — there is simply nothing to copy.
        """
        if report.id is None:
            raise ValueError("report must be persisted before use")
        if report.reference_year is None:
            return
        ref_report = await self.repo.get_calculator_report(
            report.unit_id, report.reference_year
        )
        if ref_report is None:
            return
        modules = await self.report_service.module_service.list_modules(report.id)
        prefilled_ids = sorted(
            m.module_type_id
            for m in modules
            if m.module_type_id in PLANNER_PREFILLED_MODULE_TYPES
        )
        for module_type_id in prefilled_ids:
            await self.prefill_module_from_reference(report, module_type_id)

    async def _year_read(self, report: CarbonReport) -> SimulatorPlanYearRead:
        """Build the per-year DTO (report + its modules)."""
        if report.id is None:
            raise ValueError("report must be persisted before use")
        modules = await self.report_service.module_service.list_modules(report.id)
        return SimulatorPlanYearRead(
            id=report.id,
            year=report.year,
            reference_year=report.reference_year,
            stats=report.stats,
            modules=modules,
        )

    async def prefill_module_from_reference(
        self, report: CarbonReport | CarbonReportRead, module_type_id: int
    ) -> int:
        """Snapshot-copy the reference-year Calculator entries into a plan module.

        Idempotent: previous snapshot rows (source=PLANNER_SNAPSHOT) are wiped
        and re-copied at ``percentage_of_reference_year = 100``; user-added rows
        survive. Each copy keeps ``source_data_entry_id`` so the % slider
        computes against the live reference entry. Returns the copied count.

        Raises ValueError when the report has no reference year or the
        reference year has no Calculator report/module for the unit.
        """
        if report.id is None:
            raise ValueError("report must be persisted before use")
        if report.reference_year is None:
            raise ValueError("Set a reference year before prefilling")
        module_service = self.report_service.module_service
        plan_module = await module_service.get_module(report.id, module_type_id)
        if plan_module is None or plan_module.id is None:
            raise ValueError(f"Module {module_type_id} not found on the plan year")
        ref_report = await self.repo.get_calculator_report(
            report.unit_id, report.reference_year
        )
        if ref_report is None or ref_report.id is None:
            raise ValueError(
                f"No Calculator report for reference year {report.reference_year}"
            )
        ref_module = await module_service.get_module(ref_report.id, module_type_id)
        if ref_module is None or ref_module.id is None:
            raise ValueError(f"Module {module_type_id} not found on the reference year")

        entry_repo = DataEntryRepository(self.session)
        for det in MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(
            ModuleTypeEnum(module_type_id), []
        ):
            await entry_repo.bulk_delete_by_source(
                plan_module.id, det, DataEntrySourceEnum.PLANNER_SNAPSHOT.value
            )

        emission_svc = DataEntryEmissionService(self.session)
        copied = 0
        for src in await entry_repo.list_by_module(ref_module.id):
            copy = DataEntry(
                data_entry_type_id=src.data_entry_type_id,
                carbon_report_module_id=plan_module.id,
                unit_id=report.unit_id,
                year=report.year,
                source=DataEntrySourceEnum.PLANNER_SNAPSHOT.value,
                data={
                    **src.data,
                    "percentage_of_reference_year": 100,
                    "source_data_entry_id": src.id,
                },
            )
            self.session.add(copy)
            await self.session.flush()
            await emission_svc.upsert_by_data_entry(
                DataEntryResponse.model_validate(copy)
            )
            copied += 1

        await self.report_service.module_service.recompute_stats_many([plan_module.id])
        return copied

    async def _recalculate_report_emissions(self, report: CarbonReport) -> None:
        """Recompute emissions of every entry in a report + refresh stats."""
        if report.id is None:
            raise ValueError("report must be persisted before use")
        entries = await DataEntryRepository(self.session).list_by_carbon_report(
            report.id
        )
        emission_svc = DataEntryEmissionService(self.session)
        module_ids: set[int] = set()
        for entry in entries:
            await emission_svc.upsert_by_data_entry(
                DataEntryResponse.model_validate(entry)
            )
            module_ids.add(entry.carbon_report_module_id)
        if module_ids:
            await self.report_service.module_service.recompute_stats_many(
                sorted(module_ids)
            )
        await self.report_service.recompute_report_stats(report.id)

    async def duplicate_plan(
        self, plan_id: int, user: User
    ) -> Optional[SimulatorPlanRead]:
        """Duplicate a plan as ``<name>-2`` (then ``-3``, ...); None if missing.

        The project row and its year range are copied, and the copy's per-year
        reports are synced to that range so it opens with the same year
        sections. Entry contents are not copied (empty per-year modules).
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
        await self._sync_year_reports(copy)
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
