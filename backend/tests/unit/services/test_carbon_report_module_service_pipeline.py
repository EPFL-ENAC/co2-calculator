"""Plan 310-D — service-layer tests for ``current_pipeline_id`` enrichment.

Covers ``CarbonReportModuleService.list_modules(year=...)`` end-to-end:
the service consumes the bulk repo helper
``DataIngestionRepository.get_current_pipeline_ids_for_modules`` and
populates ``CarbonReportModuleRead.current_pipeline_id`` per module.

The repo helper is unit-tested separately in
``tests/unit/repositories/test_data_ingestion_repo.py``; these tests
pin the SERVICE contract: badge appears when an active aggregation
exists, badge clears when the aggregation finishes, and the badge
respects year scoping.
"""

from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.module_type import ModuleTypeEnum
from app.models.user import UserProvider
from app.services.carbon_report_module_service import CarbonReportModuleService


def _make_aggregation_job(
    module_type_id: int,
    year: int,
    state: IngestionState,
    result: IngestionResult | None = None,
) -> DataIngestionJob:
    """Build an aggregation-shaped DataIngestionJob with a fresh
    pipeline_id.  Mirrors the rows ``chain_job(dedup_active=True,
    job_type='aggregation')`` produces in production."""
    job = DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=module_type_id,
        year=year,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        provider=UserProvider.DEFAULT,
        state=state,
        result=result,
        is_current=True,
        job_type="aggregation",
        meta={},
    )
    job.pipeline_id = uuid4()
    return job


async def _seed_report_with_module(
    db_session: AsyncSession, module_type_id: int, year: int
) -> tuple[CarbonReport, CarbonReportModule]:
    """Seed a CarbonReport + CarbonReportModule scoped to ``(module_type_id,
    year)`` so the service has something to return."""
    report = CarbonReport(year=year, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=module_type_id,
        status=ModuleStatus.NOT_STARTED,
    )
    db_session.add(module)
    await db_session.commit()
    return report, module


@pytest.mark.asyncio
async def test_list_modules_without_year_skips_pipeline_enrichment(
    db_session: AsyncSession,
):
    """Calling ``list_modules`` without ``year`` keeps the legacy
    contract — every read's ``current_pipeline_id`` stays ``None``
    even when an active pipeline exists.

    Pinning this contract means a future caller that wants the
    pre-310D shape can still get it (e.g. tests, ad-hoc scripts).
    """
    module_id = ModuleTypeEnum.equipment_electric_consumption.value
    report, _module = await _seed_report_with_module(
        db_session, module_type_id=module_id, year=2025
    )

    # Active aggregation exists for this module — but list_modules(year=None)
    # must NOT enrich.
    db_session.add(_make_aggregation_job(module_id, 2025, IngestionState.RUNNING))
    await db_session.commit()

    svc = CarbonReportModuleService(db_session)
    reads = await svc.list_modules(report.id)
    assert len(reads) == 1
    assert reads[0].current_pipeline_id is None


@pytest.mark.asyncio
async def test_list_modules_with_year_populates_active_pipeline(
    db_session: AsyncSession,
):
    """Single active aggregation in scope → ``current_pipeline_id``
    on the matching read carries that pipeline_id (the badge fires)."""
    module_id = ModuleTypeEnum.equipment_electric_consumption.value
    report, _module = await _seed_report_with_module(
        db_session, module_type_id=module_id, year=2025
    )

    aggregation = _make_aggregation_job(module_id, 2025, IngestionState.RUNNING)
    db_session.add(aggregation)
    await db_session.commit()

    svc = CarbonReportModuleService(db_session)
    reads = await svc.list_modules(report.id, year=2025)
    assert len(reads) == 1
    assert reads[0].current_pipeline_id == aggregation.pipeline_id


@pytest.mark.asyncio
async def test_list_modules_clears_pipeline_when_aggregation_finishes(
    db_session: AsyncSession,
):
    """The contract that backs the "badge clears once aggregation
    finishes" UX promise: with only FINISHED aggregations in scope,
    ``current_pipeline_id`` returns to ``None``.

    Same shape as the upstream repo unit test
    (``test_get_current_pipeline_id_skips_finished_jobs``) but pinned
    at the service layer where the API consumes it — the badge UX
    depends on this transition, not just the underlying SELECT."""
    module_id = ModuleTypeEnum.equipment_electric_consumption.value
    report, _module = await _seed_report_with_module(
        db_session, module_type_id=module_id, year=2025
    )

    finished = _make_aggregation_job(
        module_id,
        2025,
        IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
    )
    db_session.add(finished)
    await db_session.commit()

    svc = CarbonReportModuleService(db_session)
    reads = await svc.list_modules(report.id, year=2025)
    assert len(reads) == 1
    assert reads[0].current_pipeline_id is None


@pytest.mark.asyncio
async def test_list_modules_filters_by_year(
    db_session: AsyncSession,
):
    """Active aggregation for a different year must NOT bleed into
    the current year's badge.  A 2024 pipeline running in the
    background shouldn't darken the 2025 dashboard."""
    module_id = ModuleTypeEnum.equipment_electric_consumption.value
    # Report is for 2025; we ask the service for the 2025 view.
    report, _module = await _seed_report_with_module(
        db_session, module_type_id=module_id, year=2025
    )

    other_year = _make_aggregation_job(module_id, 2024, IngestionState.RUNNING)
    db_session.add(other_year)
    await db_session.commit()

    svc = CarbonReportModuleService(db_session)
    reads = await svc.list_modules(report.id, year=2025)
    assert len(reads) == 1
    assert reads[0].current_pipeline_id is None


@pytest.mark.asyncio
async def test_list_modules_only_enriches_modules_in_the_report(
    db_session: AsyncSession,
):
    """An active aggregation for a different module (not in this
    report) must not bleed into THIS report's badge — service is
    keyed by ``carbon_report_id`` first, then enriches only those
    modules.

    Defends against an N+1 → bulk refactor regression where we
    might accidentally enrich every module that has an active
    pipeline regardless of which report we're asking about."""
    in_report = ModuleTypeEnum.equipment_electric_consumption.value
    not_in_report = ModuleTypeEnum.professional_travel.value
    report, _module = await _seed_report_with_module(
        db_session, module_type_id=in_report, year=2025
    )

    # Only the not-in-report module has an active pipeline.
    db_session.add(_make_aggregation_job(not_in_report, 2025, IngestionState.RUNNING))
    await db_session.commit()

    svc = CarbonReportModuleService(db_session)
    reads = await svc.list_modules(report.id, year=2025)
    assert len(reads) == 1
    assert reads[0].module_type_id == in_report
    assert reads[0].current_pipeline_id is None
