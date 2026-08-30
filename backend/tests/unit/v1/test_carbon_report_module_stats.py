"""Unit tests for carbon_report_module_stats API endpoints.

Focus: build_validated_totals derives validated_only from the DB-stored
CarbonProject.carbon_report_type rather than any client-supplied signal, and
reads persisted module stats instead of re-aggregating emissions.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.api.v1.carbon_report_module_stats as stats_module
from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReportType
from app.models.module_type import ModuleTypeEnum

_HEADCOUNT = ModuleTypeEnum.headcount.value

# (module_type_id, status, stats): one validated emissions module, one
# in-progress module, and a validated headcount module carrying FTE.
_MODULE_ROWS = [
    (
        ModuleTypeEnum.equipment.value,
        ModuleStatus.VALIDATED,
        {"total": 41700.0},
    ),
    (
        ModuleTypeEnum.professional_travel.value,
        ModuleStatus.IN_PROGRESS,
        {"total": 15000.0},
    ),
    (
        _HEADCOUNT,
        ModuleStatus.VALIDATED,
        {"total": 200.0, "total_fte": 25.5},
    ),
]


def _db(report_type: CarbonReportType | None, report_id: int = 1):
    """Session whose single module-stats read returns ``_MODULE_ROWS``.

    One statement, not two: the project type now rides the same grouped query
    as the module rows (#2527 task 4).
    """
    db = MagicMock()
    rows_result = MagicMock()
    rows_result.all.return_value = [
        (report_id, module_type_id, module_status, stats, report_type)
        for module_type_id, module_status, stats in _MODULE_ROWS
    ]
    db.execute = AsyncMock(return_value=rows_result)
    return db


@pytest.mark.asyncio
async def test_build_validated_totals_calculator_uses_validated_only():
    """CALCULATOR report → only VALIDATED module stats count."""
    result = await stats_module.build_validated_totals(
        _db(CarbonReportType.CALCULATOR), 1
    )

    assert result["modules"][ModuleTypeEnum.equipment.value] == 41.7
    # headcount displays FTE, not tonnes
    assert result["modules"][_HEADCOUNT] == 25.5
    assert ModuleTypeEnum.professional_travel.value not in result["modules"]
    assert result["total_tonnes_co2eq"] == pytest.approx((41700.0 + 200.0) / 1000.0)
    assert result["total_fte"] == 25.5


@pytest.mark.asyncio
async def test_build_validated_totals_simulator_explore_counts_all_modules():
    """SIMULATOR_EXPLORE has no validation step → every module counts."""
    result = await stats_module.build_validated_totals(
        _db(CarbonReportType.SIMULATOR_EXPLORE), 1
    )

    assert ModuleTypeEnum.professional_travel.value in result["modules"]
    assert result["total_tonnes_co2eq"] == pytest.approx(
        (41700.0 + 15000.0 + 200.0) / 1000.0
    )


@pytest.mark.asyncio
async def test_build_validated_totals_simulator_plan_uses_validated_only():
    """SIMULATOR_PLAN → validated_only (only EXPLORE relaxes validation)."""
    result = await stats_module.build_validated_totals(
        _db(CarbonReportType.SIMULATOR_PLAN), 1
    )

    assert ModuleTypeEnum.professional_travel.value not in result["modules"]


@pytest.mark.asyncio
async def test_build_validated_totals_unknown_report_id_uses_validated_only():
    """Unknown carbon_report_id (DB returns None) → validated_only safe default."""
    result = await stats_module.build_validated_totals(_db(None), 1)

    assert ModuleTypeEnum.professional_travel.value not in result["modules"]


@pytest.mark.asyncio
async def test_build_validated_totals_by_report_is_one_query_for_many_reports():
    """R reports cost one statement, not 2R (#2527 task 4)."""
    db = MagicMock()
    rows_result = MagicMock()
    rows_result.all.return_value = [
        (report_id, module_type_id, module_status, stats, CarbonReportType.CALCULATOR)
        for report_id in (1, 2, 3)
        for module_type_id, module_status, stats in _MODULE_ROWS
    ]
    db.execute = AsyncMock(return_value=rows_result)

    totals = await stats_module.build_validated_totals_by_report(db, [1, 2, 3])

    assert db.execute.await_count == 1
    assert sorted(totals) == [1, 2, 3]
    assert totals[2]["total_tonnes_co2eq"] == pytest.approx((41700.0 + 200.0) / 1000.0)


@pytest.mark.asyncio
async def test_build_validated_totals_report_without_modules_is_zero():
    """A report with no module rows folds to zero rather than raising."""
    db = MagicMock()
    rows_result = MagicMock()
    rows_result.all.return_value = []
    db.execute = AsyncMock(return_value=rows_result)

    result = await stats_module.build_validated_totals(db, 99)

    assert result["total_tonnes_co2eq"] == 0.0
    assert result["modules"] == {}
