"""Simulator plan service for business logic.

A "plan" (project planner project) is a ``CarbonProject`` row with
``carbon_report_type = SIMULATOR_PLAN``; its ``name`` is the URL identifier
shown in the project planner routes.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportType
from app.models.data_entry import (
    DataEntry,
    DataEntrySourceEnum,
    DataEntryStatusEnum,
    DataEntryTypeEnum,
)
from app.models.data_entry_emission import DataEntryEmissionRow
from app.models.module_type import (
    PLANNER_PLAIN_COPY_MODULE_TYPES,
    PLANNER_PREFILLED_MODULE_TYPES,
    PLANNER_REFERENCE_SCOPED_MODULE_TYPES,
    ModuleTypeEnum,
)
from app.models.user import User
from app.modules_planner.headcount import PLANNER_STUDENT_CODE
from app.repositories.carbon_project_repo import CarbonProjectRepository
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.carbon_report import (
    CarbonReportCreate,
    CarbonReportModuleRead,
    CarbonReportRead,
)
from app.schemas.data_entry import BaseModuleHandler, DataEntryResponse
from app.schemas.simulator_plan import (
    SimulatorPlanRead,
    SimulatorPlanUpdate,
    SimulatorPlanYearRead,
)
from app.services.carbon_report_service import CarbonReportService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.factor_resolver import FactorResolver
from app.utils.factor_year import resolve_factor_year
from app.utils.report_stats import merge_report_stats

logger = get_logger(__name__)

DEFAULT_PLAN_NAME = "new-project"


@dataclass
class _ReferenceCache:
    """The reference year's side of a prefill, read once per job.

    Every plan year of one plan copies from the *same* reference report,
    so without this the job re-reads that report, its modules and — the
    expensive part — all of its entries once per year: 40 of the 90
    ``list_by_module`` calls in a measured 10-year prefill were the same
    rows fetched ten times (plan #2050 Track F6).
    """

    reports: dict[tuple[int, int], CarbonReport | None] = field(default_factory=dict)
    modules: dict[int, dict[int, CarbonReportModuleRead]] = field(default_factory=dict)
    entries: dict[int, list[DataEntry]] = field(default_factory=dict)


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
    creator_name: str | None,
    total_tonnes_co2eq: float | None = None,
    default_factor_year: int | None = None,
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
        is_grant_proposal=project.is_grant_proposal,
        created_by=project.created_by,
        created_at=project.created_at,
        creator_name=creator_name,
        total_tonnes_co2eq=total_tonnes_co2eq,
        default_factor_year=default_factor_year,
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
        default_factor_year = await self.repo.get_latest_calculator_year(unit_id)
        return [
            _to_read(
                project,
                creator_name,
                totals.get(project.id or -1),
                default_factor_year,
            )
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

    async def get_plan(self, plan_id: int) -> SimulatorPlanRead | None:
        """Get a plan by ID, or None."""
        row = await self.repo.get_plan_with_creator(plan_id)
        if row is None:
            return None
        project, creator_name = row
        return _to_read(
            project,
            creator_name,
            default_factor_year=await self.repo.get_latest_calculator_year(
                project.unit_id
            ),
        )

    async def create_plan(
        self, *, unit_id: int, user: User, name: str | None = None
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
            created_at=datetime.now(UTC),
        )
        project = await self._flush_guarded(self.repo.create(project))
        return _to_read(
            project,
            user.display_name,
            default_factor_year=await self.repo.get_latest_calculator_year(unit_id),
        )

    async def update_plan(
        self, plan_id: int, update: SimulatorPlanUpdate
    ) -> tuple[SimulatorPlanRead, list[int]] | None:
        """Apply a PATCH to a plan; returns None if the plan does not exist.

        Returns the updated plan and the report ids still needing prefill —
        the caller enqueues that work (plan #2050 Track F4).

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
        if update.is_grant_proposal is not None:
            project.is_grant_proposal = update.is_grant_proposal
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
        needs_prefill = await self._sync_year_reports(
            project,
            default_reference_year=update.default_reference_year,
            with_year_sections=update.with_year_sections,
        )
        return await self._read_with_creator(project), needs_prefill

    async def _sync_year_reports(
        self,
        project: CarbonProject,
        default_reference_year: int | None = None,
        *,
        with_year_sections: bool | None = None,
    ) -> list[int]:
        """Make the plan's reports match ``start_year..end_year``, one per year.

        Out-of-range reports are deleted together with their entries
        (destructive by design — the user shrank the range deliberately).
        Until both bounds are set, only the grant report is synced.

        Newly created year reports default their reference year to
        ``default_reference_year`` (the workspace year the range was set
        from) and are prefilled from it, exactly as if the user had picked
        it in the dialog. Existing reports keep their reference year.

        ``with_year_sections`` opts the plan out of (or back into) per-year
        reports; ``None`` keeps the plan's current shape, derived from its
        existing non-grant reports (a plan with no reports yet gets them).
        A plan must keep either its year sections or its grant proposal.

        A plan that ends up with per-year sections is also forced back to
        private (``is_viewable_by_unit_members = False``): those sections
        carry the unit's real annual data, which only the creator may see.

        Returns the ids of the reports that still need prefilling. Creating
        the reports is cheap; copying a reference year into them is not (a
        10-year range over a large baseline runs to tens of thousands of
        rows), so that part is handed to the ``simulator_plan_prefill`` job
        rather than run inside the request — plan #2050 Track F4.
        """
        if project.id is None:
            raise ValueError("project must be persisted before use")
        reports = await self.repo.list_reports_for_project(project.id)
        grant_report = next((r for r in reports if r.is_grant), None)
        if project.start_year is None or project.end_year is None:
            await self._sync_grant_report(project, grant_report)
            return []
        want_years = with_year_sections
        if want_years is None:
            want_years = not reports or any(not r.is_grant for r in reports)
        if not want_years and not project.is_grant_proposal:
            raise ValueError("A plan needs year-by-year sections or a grant proposal")
        target_years = (
            set(range(project.start_year, project.end_year + 1))
            if want_years
            else set()
        )
        existing_years: set[int] = set()
        for report in reports:
            if report.is_grant:
                continue
            if report.year in target_years:
                existing_years.add(report.year)
            elif report.id is not None:
                await self.report_service.delete(report.id)
        needs_prefill: list[int] = []
        for year in sorted(target_years - existing_years):
            report_read = await self.report_service.create(
                CarbonReportCreate(
                    unit_id=project.unit_id,
                    year=year,
                    carbon_project_id=project.id,
                    reference_year=default_reference_year,
                )
            )
            if default_reference_year is not None:
                needs_prefill.append(report_read.id)
        if want_years and project.is_viewable_by_unit_members:
            project.is_viewable_by_unit_members = False
            self.session.add(project)
            await self.session.flush()
        await self._sync_grant_report(project, grant_report)
        return needs_prefill

    async def _sync_grant_report(
        self, project: CarbonProject, grant_report: CarbonReport | None
    ) -> None:
        """Make the plan's Project Grant report match ``is_grant_proposal``.

        Unchecking the checkbox deletes the grant report together with its
        entries (destructive by design, like shrinking the year range). The
        report is anchored to the plan's start year — or the current year
        until one is set: when the range moves (or arrives) it follows,
        keeping its data — grant entries resolve their factors from the
        reference year, not the report year.
        """
        if not project.is_grant_proposal:
            if grant_report is not None and grant_report.id is not None:
                await self.report_service.delete(grant_report.id)
            return
        if project.id is None:
            return
        if grant_report is None:
            await self.report_service.create(
                CarbonReportCreate(
                    unit_id=project.unit_id,
                    year=project.start_year or datetime.now(UTC).year,
                    carbon_project_id=project.id,
                    is_grant=True,
                )
            )
        elif project.start_year is not None and grant_report.year != project.start_year:
            grant_report.year = project.start_year
            self.session.add(grant_report)
            await self.session.flush()

    async def list_plan_years(self, plan_id: int) -> list[SimulatorPlanYearRead] | None:
        """List the plan's per-year reports with their modules, by year.

        Returns None when the plan does not exist (vs. [] for a plan whose
        year range is not set yet).
        """
        project = await self.repo.get_plan(plan_id)
        if project is None:
            return None
        if project.id is None:
            raise ValueError("project must be persisted before use")
        reports = await self.repo.list_reports_for_project(project.id)
        # The Project Grant section renders before the year sections.
        reports.sort(key=lambda r: (not r.is_grant, r.year))
        return [await self._year_read(report) for report in reports]

    async def set_reference_year(
        self,
        plan_id: int,
        year: int,
        reference_year: int | None,
        *,
        is_grant: bool = False,
    ) -> tuple[SimulatorPlanYearRead, list[int]] | None:
        """Set or remove the baseline year of one plan-year report; None if missing.

        ``is_grant`` targets the Project Grant report, which shares its year
        with the start-year report.

        Destructive: every reference-scoped module of the plan-year is emptied
        and, when a baseline is set, the prefilled ones are rebuilt from it at
        100% (purchase stays empty) — the percentages,
        edits and hand-added rows made under the previous reference year are
        lost. Removing the baseline (``reference_year=None``) empties them
        the same way and leaves the year manual-input. The dialog warns
        about it before calling this.

        The remaining entries get their emissions recomputed, since factor
        lookup follows the reference year — deferred to the
        ``simulator_plan_prefill`` job, whose id the caller returns so the
        client can wait for it (plan #2050 Track F4). Returns the year and
        the report ids needing that work; an unchanged baseline needs none.
        """
        reports = await self.repo.list_reports_for_project(plan_id)
        report = next(
            (r for r in reports if r.year == year and r.is_grant == is_grant), None
        )
        if report is None:
            return None
        needs_prefill: list[int] = []
        if report.reference_year != reference_year:
            report.reference_year = reference_year
            self.session.add(report)
            await self.session.flush()
            if report.id is not None:
                needs_prefill.append(report.id)
        return await self._year_read(report), needs_prefill

    async def prefill_reports(self, report_ids: list[int]) -> int:
        """Prefill and recompute whole reports; returns how many ran.

        The ``simulator_plan_prefill`` job's entry point (plan #2050 Track
        F4) — the expensive half of both plan PATCHes, lifted out of the
        request. Safe to re-run after a crashed or preempted job: prefill
        empties each module before rebuilding it, so a retry converges
        instead of duplicating rows.

        Prefill only inserts the copied rows; the recalc right after
        computes every entry's emissions (and every touched module's stats)
        from scratch — it has to, since it also covers modules prefill never
        touches, like purchase's manual rows.
        """
        reports = await self.repo.list_reports_by_ids(report_ids)
        ref_cache = _ReferenceCache()
        for report in reports:
            await self._prefill_reference_modules(report, ref_cache=ref_cache)
            await self._recalculate_report_emissions(report)
        return len(reports)

    async def _prefill_reference_modules(
        self,
        report: CarbonReport | CarbonReportRead,
        *,
        ref_cache: _ReferenceCache | None = None,
    ) -> None:
        """Empty every reference-scoped module, rebuild prefilled + copied ones.

        Runs on reference-year set/change/removal (there is no manual prefill
        trigger). The modules are emptied first, so a module never mixes two
        baselines; on removal the wipe is all that happens and the year
        becomes manual-input. Purchase is wiped without a rebuild — it is
        manual input, but its classes and factors come from the reference
        year, so its rows do not survive a new baseline (#1920). When the reference year
        has no Calculator report for the unit there is nothing to copy and they stay
        empty —  showing the previous baseline's rows under a new reference year
        would be a lie.

        Inserts the copied rows only; the caller computes emissions for the
        whole report in one batched pass right after (both callers do — plan
        #2050 Track F2).

        ``ref_cache`` lets a multi-report job read the reference side once
        instead of once per plan year; omit it and this call reads its own
        (plan #2050 Track F6).
        """
        if report.id is None:
            raise ValueError("report must be persisted before use")
        modules = await self.report_service.module_service.list_modules(report.id)
        scoped = [
            m
            for m in modules
            if m.module_type_id in PLANNER_REFERENCE_SCOPED_MODULE_TYPES
        ]
        rebuilt = [
            m
            for m in scoped
            if m.module_type_id
            in PLANNER_PREFILLED_MODULE_TYPES | PLANNER_PLAIN_COPY_MODULE_TYPES
        ]

        ref_report = None
        if report.reference_year is not None:
            ref_key = (report.unit_id, report.reference_year)
            if ref_cache is not None and ref_key in ref_cache.reports:
                ref_report = ref_cache.reports[ref_key]
            else:
                ref_report = await self.repo.get_calculator_report(
                    report.unit_id, report.reference_year
                )
                if ref_cache is not None:
                    ref_cache.reports[ref_key] = ref_report
        # The grant RF grid starts from the reference year's platform list,
        # not from copied entries (#1980) — left empty for the user's own
        # selection. Grant travel is planned from scratch too (#2018). Both
        # stay out of ``will_rebuild`` below, which decides both what gets
        # prefilled and what the upfront clear must still cover — they
        # never self-clear (prefill is never called for them), so the
        # upfront clear is their only chance to empty out.
        will_rebuild = (
            [
                m
                for m in rebuilt
                if not (
                    report.is_grant
                    and m.module_type_id
                    in (
                        ModuleTypeEnum.research_facilities,
                        ModuleTypeEnum.professional_travel,
                    )
                )
            ]
            if ref_report is not None
            else []
        )
        will_rebuild_ids = {m.module_type_id for m in will_rebuild}
        # Only clear modules upfront that won't self-clear when rebuilt
        # below — prefill_module_from_reference/prefill_headcount_from_
        # reference each delete-then-rebuild their own module already
        # (plan #2050 Track D finding 1); clearing them here too is
        # thrown-away work, never observable (nothing commits mid-request).
        cleared = [
            m.id
            for m in scoped
            if m.id is not None and m.module_type_id not in will_rebuild_ids
        ]
        await self._clear_module_entries(cleared)
        if ref_report is None or ref_report.id is None or not will_rebuild_ids:
            if cleared:
                await self.report_service.module_service.recompute_stats_many(
                    sorted(cleared)
                )
            return
        # One list_modules for the reference side (the plan side is already
        # `modules`/`will_rebuild`, fetched once above) instead of one
        # get_module per module type on each side — a real get_module call
        # for every rebuilt type, twice, otherwise (plan #2050 Track E
        # tier 2).
        if ref_cache is not None and ref_report.id in ref_cache.modules:
            ref_modules_by_type = ref_cache.modules[ref_report.id]
        else:
            ref_modules_by_type = {
                m.module_type_id: m
                for m in await self.report_service.module_service.list_modules(
                    ref_report.id
                )
            }
            if ref_cache is not None:
                ref_cache.modules[ref_report.id] = ref_modules_by_type
        plan_modules_by_type = {m.module_type_id: m for m in will_rebuild}
        emptied: list[int] = []
        for module_type_id in sorted(will_rebuild_ids):
            plan_module = plan_modules_by_type[module_type_id]
            if module_type_id == ModuleTypeEnum.headcount:
                copied = await self.prefill_headcount_from_reference(
                    report,
                    ref_report=ref_report,
                    plan_module=plan_module,
                    ref_module=ref_modules_by_type.get(module_type_id),
                    ref_cache=ref_cache,
                )
            else:
                copied = await self.prefill_module_from_reference(
                    report,
                    module_type_id,
                    ref_report=ref_report,
                    plan_module=plan_module,
                    ref_module=ref_modules_by_type.get(module_type_id),
                    ref_cache=ref_cache,
                )
            if copied == 0 and plan_module.id is not None:
                emptied.append(plan_module.id)
        # Modules cleared above and modules prefill left empty are the same
        # case — neither appears in _recalculate_report_emissions's
        # entry-driven module set, so both need a stats refresh here. One
        # call for all of them keeps the report rollup behind it to a single
        # run per report (plan #2050 Track F6).
        stale = cleared + emptied
        if stale:
            await self.report_service.module_service.recompute_stats_many(sorted(stale))

    async def _reference_entries(
        self,
        ref_module_id: int,
        ref_cache: _ReferenceCache | None,
    ) -> list[DataEntry]:
        """The reference module's entries, read once per job when cached.

        These are the rows every plan year copies, so a 10-year prefill
        otherwise fetches the same set ten times (plan #2050 Track F6).
        """
        if ref_cache is not None and ref_module_id in ref_cache.entries:
            return ref_cache.entries[ref_module_id]
        entries = await DataEntryRepository(self.session).list_by_module(ref_module_id)
        if ref_cache is not None:
            ref_cache.entries[ref_module_id] = entries
        return entries

    async def _clear_module_entries(self, module_ids: list[int]) -> None:
        """Delete every data entry of the given modules.

        Emissions follow through the ``data_entry_id`` cascade. Stats are
        *not* refreshed here: the caller folds these modules in with the
        ones prefill leaves empty and refreshes both in a single
        ``recompute_stats_many``, so the report rollup behind it runs once
        per report instead of once per group (plan #2050 Track F6).
        """
        if not module_ids:
            return
        await DataEntryRepository(self.session).bulk_delete_by_modules(module_ids)

    async def _year_read(self, report: CarbonReport) -> SimulatorPlanYearRead:
        """Build the per-year DTO (report + its modules)."""
        if report.id is None:
            raise ValueError("report must be persisted before use")
        modules = await self.report_service.module_service.list_modules(report.id)
        return SimulatorPlanYearRead(
            id=report.id,
            year=report.year,
            reference_year=report.reference_year,
            is_grant=report.is_grant,
            budget=report.budget,
            budget_currency=report.budget_currency,
            stats=report.stats,
            modules=modules,
        )

    async def prefill_module_from_reference(
        self,
        report: CarbonReport | CarbonReportRead,
        module_type_id: int,
        *,
        ref_report: CarbonReport | None = None,
        plan_module: CarbonReportModuleRead | None = None,
        ref_module: CarbonReportModuleRead | None = None,
        ref_cache: _ReferenceCache | None = None,
    ) -> int:
        """Rebuild a plan module from the reference-year Calculator entries.

        Destructive and idempotent: the module's entries are deleted first, then
        the reference year's are copied at ``percentage_of_reference_year =
        100``. Each copy keeps ``source_data_entry_id`` so the % slider computes
        against the live reference entry. Plain-copy modules
        (``PLANNER_PLAIN_COPY_MODULE_TYPES``) skip both fields: their copies are
        ordinary editable entries whose emissions recompute from the row data.
        Returns the copied count.

        Emissions are not computed here — the caller recomputes the whole
        report in one batched pass right after (plan #2050 Track F2).

        Args:
            ref_report: The reference year's Calculator report, when the
                caller (``_prefill_reference_modules``) already looked it up
                for the whole rebuild — skips the redundant refetch here.
            plan_module: The plan-year's own module, when the caller already
                has it (``_prefill_reference_modules`` always does — it
                lists every module up front) — skips the redundant
                ``get_module`` here (plan #2050 Track E tier 2).
            ref_module: Same, for the reference year's module.

        Raises ValueError when the report has no reference year or the
        reference year has no Calculator report/module for the unit.
        """
        if report.id is None:
            raise ValueError("report must be persisted before use")
        if report.reference_year is None:
            raise ValueError("Set a reference year before prefilling")
        module_service = self.report_service.module_service
        if plan_module is None:
            plan_module = await module_service.get_module(report.id, module_type_id)
        if plan_module is None or plan_module.id is None:
            raise ValueError(f"Module {module_type_id} not found on the plan year")
        if ref_report is None:
            ref_report = await self.repo.get_calculator_report(
                report.unit_id, report.reference_year
            )
        if ref_report is None or ref_report.id is None:
            raise ValueError(
                f"No Calculator report for reference year {report.reference_year}"
            )
        if ref_module is None:
            ref_module = await module_service.get_module(ref_report.id, module_type_id)
        if ref_module is None or ref_module.id is None:
            raise ValueError(f"Module {module_type_id} not found on the reference year")

        entry_repo = DataEntryRepository(self.session)
        await entry_repo.bulk_delete_by_modules([plan_module.id])

        src_entries = await self._reference_entries(ref_module.id, ref_cache)
        if not src_entries:
            # Returning 0 tells _prefill_reference_modules this module ended
            # up empty; it batches every such module's stats refresh into one
            # call instead of one per module (plan #2050 Track F6).
            return 0
        # Grant equipment plans from scratch: every prefilled line starts at
        # 0% and the user raises what the project actually uses (#1981).
        # Everywhere else the snapshot starts as a full copy of the baseline.
        default_percentage = (
            0 if report.is_grant and module_type_id == ModuleTypeEnum.equipment else 100
        )
        plain_copy = module_type_id in PLANNER_PLAIN_COPY_MODULE_TYPES
        rows = [
            {
                "data_entry_type_id": src.data_entry_type_id,
                "carbon_report_module_id": plan_module.id,
                "unit_id": report.unit_id,
                "year": report.year,
                "source": DataEntrySourceEnum.PLANNER_SNAPSHOT.value,
                "status": DataEntryStatusEnum.PENDING,
                "created_by_id": None,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
                "data": dict(src.data)
                if plain_copy
                else {
                    **src.data,
                    "percentage_of_reference_year": default_percentage,
                    "source_data_entry_id": src.id,
                },
            }
            for src in src_entries
        ]
        await self._bulk_insert_entries(rows)
        return len(rows)

    async def prefill_headcount_from_reference(
        self,
        report: CarbonReport | CarbonReportRead,
        *,
        ref_report: CarbonReport | None = None,
        plan_module: CarbonReportModuleRead | None = None,
        ref_module: CarbonReportModuleRead | None = None,
        ref_cache: _ReferenceCache | None = None,
    ) -> int:
        """Rebuild the plan's headcount grid from the reference-year members.

        Not a one-to-one copy like the other prefilled modules: the Calculator
        holds one row per person, the planner grid one row per SIUS category,
        so the members' FTE are summed by category, and the student entries into
        the grid's own students row. Each row starts at the reference year's full
        FTE, for the user to lower to the project's share; a category nobody
        staffed gets no row, leaving its input blank. Destructive and
        idempotent — the grid is emptied first. Returns the rows created.

        Args:
            plan_module: see ``prefill_module_from_reference``'s docstring —
                same contract (plan #2050 Track E tier 2).
            ref_module: same.
        """
        if report.id is None:
            raise ValueError("report must be persisted before use")
        if report.reference_year is None:
            raise ValueError("Set a reference year before prefilling")
        module_service = self.report_service.module_service
        if plan_module is None:
            plan_module = await module_service.get_module(
                report.id, ModuleTypeEnum.headcount
            )
        if plan_module is None or plan_module.id is None:
            raise ValueError("Headcount module not found on the plan year")
        if ref_report is None:
            ref_report = await self.repo.get_calculator_report(
                report.unit_id, report.reference_year
            )
        if ref_report is None or ref_report.id is None:
            raise ValueError(
                f"No Calculator report for reference year {report.reference_year}"
            )
        if ref_module is None:
            ref_module = await module_service.get_module(
                ref_report.id, ModuleTypeEnum.headcount
            )
        if ref_module is None or ref_module.id is None:
            raise ValueError("Headcount module not found on the reference year")

        entry_repo = DataEntryRepository(self.session)
        await entry_repo.bulk_delete_by_modules([plan_module.id])

        fte_by_code: dict[str, float] = {}
        for src in await self._reference_entries(ref_module.id, ref_cache):
            if src.data_entry_type_id == DataEntryTypeEnum.member:
                code = src.data.get("sius_code")
            elif src.data_entry_type_id == DataEntryTypeEnum.student:
                code = PLANNER_STUDENT_CODE
            else:
                continue
            if not code:
                continue
            try:
                fte = float(src.data.get("fte") or 0)
            except TypeError, ValueError:
                logger.warning(
                    "Skipping headcount entry %r with non-numeric fte=%r",
                    src.id,
                    src.data.get("fte"),
                )
                continue
            fte_by_code[code] = fte_by_code.get(code, 0.0) + fte

        row_dicts = [
            {
                "data_entry_type_id": DataEntryTypeEnum.planner_headcount.value,
                "carbon_report_module_id": plan_module.id,
                "unit_id": report.unit_id,
                "year": report.year,
                "source": DataEntrySourceEnum.PLANNER_SNAPSHOT.value,
                "status": DataEntryStatusEnum.PENDING,
                "created_by_id": None,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
                "data": {"sius_code": code, "fte": fte},
            }
            for code, fte in sorted(fte_by_code.items())
            if fte > 0
        ]
        rows = await self._bulk_insert_entries(row_dicts)
        # An empty result is reported to the caller (see
        # prefill_module_from_reference) rather than refreshing stats here:
        # an empty module never appears in _recalculate_report_emissions's
        # entry-driven module set, so it still needs one — batched.
        return len(rows)

    async def _bulk_insert_entries(self, rows: list[dict]) -> list[DataEntryResponse]:
        """INSERT ``rows`` via Core, wrapping each with its assigned id.

        Returns the ``DataEntryResponse`` shape ``prepare_create``
        already accepts — no ``DataEntry(...)`` ORM
        instance is ever constructed for a prefill batch, since these rows
        are never individually ``session.add()``ed (only ``create``/
        ``upsert_by_data_entry`` need that — see
        ``DataEntryEmissionRow``'s docstring for the same pattern one model
        over). Plan #2050 §C2/C3 follow-up: this is what the request's
        remaining `INSERT INTO data_entries` + preceding gap in a live trace
        turned out to be — per-row SQLAlchemy mapper/instance-state
        overhead, not a query-count problem (that part was already fixed).
        """
        if not rows:
            return []
        ids = await DataEntryRepository(self.session).bulk_insert_returning_ids(rows)
        return [
            DataEntryResponse(
                id=row_id,
                data_entry_type_id=row["data_entry_type_id"],
                carbon_report_module_id=row["carbon_report_module_id"],
                data=row["data"],
                source=row["source"],
                status=row["status"],
            )
            for row_id, row in zip(ids, rows, strict=True)
        ]

    async def _recalculate_report_emissions(
        self, report: CarbonReport | CarbonReportRead
    ) -> None:
        """Recompute emissions of the report's entries + refresh stats.

        Factor lookup follows the reference year, so every entry of the report
        has to be recomputed when it changes.

        Batched like the recalc workflow — see
        ``_prepare_recalc_emissions`` — instead of the old per-entry
        ``upsert_by_data_entry`` loop, measured at 39x more SQL statements
        for a 40x entry-count increase (plan #2050 section C3).
        """
        if report.id is None:
            raise ValueError("report must be persisted before use")
        entries = await DataEntryRepository(self.session).list_by_carbon_report(
            report.id
        )
        if not entries:
            # No per-entry compute to batch, but the report-level rollup
            # still needs a refresh — a report that just lost its last entry
            # must not keep stale stats/completion_progress (matches the
            # unconditional recompute_report_stats the old per-entry loop
            # always ran, unlike the module-stats call it gated on entries).
            await self.report_service.recompute_report_stats(report.id)
            return

        # Pure function of ``report`` (reference year wins) — same value for
        # every entry below, so it is computed once instead of once per entry.
        year = await resolve_factor_year(self.session, report)
        entry_ids, prepared_emissions = await self._prepare_recalc_emissions(
            entries, year=year, unit_id=report.unit_id
        )
        emission_svc = DataEntryEmissionService(self.session)
        await emission_svc.bulk_replace_for_entries(entry_ids, prepared_emissions)

        module_ids = {entry.carbon_report_module_id for entry in entries}
        await self.report_service.module_service.recompute_stats_many(
            sorted(module_ids)
        )
        await self.report_service.recompute_report_stats(report.id)

    async def _prepare_recalc_emissions(
        self, entries: list[DataEntry], *, year: int | None, unit_id: int | None
    ) -> tuple[list[int], list[DataEntryEmissionRow]]:
        """Compute emissions for ``entries``, sharing resolver/cache/slice state.

        Groups by ``data_entry_type_id`` (a report mixes module types, each
        with its own handler and ``prefetch_slice``) so an N-entry report
        costs one shared ``FactorResolver`` + factor-query cache and one
        ``prefetch_slice`` per type, not one factor lookup per entry.

        Plan-year entries are prefill copies and so all carry
        ``percentage_of_reference_year`` + ``source_data_entry_id`` — also
        prefetch the override sums for the whole batch up front instead of
        one PK fetch + one sum query per entry (plan #2050 section C3).
        """
        emission_svc = DataEntryEmissionService(self.session)
        factor_resolver = FactorResolver(self.session)
        factor_query_cache: dict = {}
        override_cache = await emission_svc.prefetch_percentage_override_cache(
            entries, unit_id=unit_id
        )

        by_type: dict[int, list[DataEntry]] = {}
        for entry in entries:
            by_type.setdefault(entry.data_entry_type_id, []).append(entry)

        entry_ids: list[int] = []
        prepared_emissions: list[DataEntryEmissionRow] = []
        for data_entry_type_id, group in by_type.items():
            handler = BaseModuleHandler.get_by_type(
                DataEntryTypeEnum(data_entry_type_id)
            )
            slice_cache = await handler.prefetch_slice(group, self.session, year=year)
            for entry in group:
                if entry.id is not None:
                    entry_ids.append(entry.id)
                prepared_emissions.extend(
                    await emission_svc.prepare_create(
                        DataEntryResponse.model_validate(entry),
                        year=year,
                        factor_resolver=factor_resolver,
                        factor_query_cache=factor_query_cache,
                        slice_cache=slice_cache,
                        override_cache=override_cache,
                    )
                )
        return entry_ids, prepared_emissions

    async def duplicate_plan(
        self, plan_id: int, user: User
    ) -> SimulatorPlanRead | None:
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
            is_grant_proposal=source.is_grant_proposal,
            created_by=user.id,
            created_at=datetime.now(UTC),
        )
        copy = await self._flush_guarded(self.repo.create(copy))
        # The copy has no reports yet, so its shape (with or without per-year
        # sections) cannot be derived from itself — carry the source's over.
        source_reports = await self.repo.list_reports_for_project(plan_id)
        await self._sync_year_reports(
            copy,
            with_year_sections=not source_reports
            or any(not r.is_grant for r in source_reports),
        )
        return _to_read(
            copy,
            user.display_name,
            default_factor_year=await self.repo.get_latest_calculator_year(
                copy.unit_id
            ),
        )

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
        default_factor_year = await self.repo.get_latest_calculator_year(
            project.unit_id
        )
        row = await self.repo.get_plan_with_creator(project.id or -1)
        if row is None:
            return _to_read(project, None, default_factor_year=default_factor_year)
        refreshed, creator_name = row
        return _to_read(
            refreshed, creator_name, default_factor_year=default_factor_year
        )

    @staticmethod
    async def _flush_guarded(awaitable) -> CarbonProject:
        """Await a repo write, mapping unique-index races to ValueError."""
        try:
            return await awaitable
        except IntegrityError as exc:
            raise ValueError(
                "A plan with this name already exists for this unit"
            ) from exc
