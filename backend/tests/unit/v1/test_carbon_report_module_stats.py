"""Unit tests for carbon_report_module_stats API endpoints.

Focus: get_validated_totals derives validated_only from the DB-stored
CarbonProject.carbon_report_type rather than any client-supplied signal.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.api.v1.carbon_report_module_stats as stats_module
from app.models.carbon_report import CarbonReportType


def _db():
    db = MagicMock()
    db.commit = AsyncMock()
    return db


def _user():
    return MagicMock()


def _mock_db_execute(db: MagicMock, report_type: CarbonReportType | None) -> None:
    """Wire db.execute to return the given report_type from scalar_one_or_none."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = report_type
    db.execute = AsyncMock(return_value=mock_result)


async def _call_validated_totals(db, report_type: CarbonReportType | None) -> dict:
    """Helper: stub services, call get_validated_totals, return call-arg capture."""
    _mock_db_execute(db, report_type)

    emission_svc = MagicMock()
    emission_svc.get_stats_by_carbon_report_id = AsyncMock(return_value={})
    fte_svc = MagicMock()
    fte_svc.get_stats_by_carbon_report_id = AsyncMock(return_value={})

    orig_emission = stats_module.DataEntryEmissionService
    orig_fte = stats_module.DataEntryService
    orig_compute = stats_module.compute_validated_totals
    stats_module.DataEntryEmissionService = lambda _db: emission_svc
    stats_module.DataEntryService = lambda _db: fte_svc
    stats_module.compute_validated_totals = lambda *a, **kw: {}
    try:
        await stats_module.get_validated_totals(1, db, _user())
    finally:
        stats_module.DataEntryEmissionService = orig_emission
        stats_module.DataEntryService = orig_fte
        stats_module.compute_validated_totals = orig_compute

    return {"emission_svc": emission_svc, "fte_svc": fte_svc}


# ── get_validated_totals: server-side type check ──────────────────────────────


@pytest.mark.asyncio
async def test_get_validated_totals_calculator_uses_validated_only_true():
    """CALCULATOR report → validated_only=True (server derives from DB, not client)."""
    db = _db()
    svcs = await _call_validated_totals(db, CarbonReportType.CALCULATOR)

    svcs["emission_svc"].get_stats_by_carbon_report_id.assert_awaited_once_with(
        carbon_report_id=1, validated_only=True
    )
    svcs["fte_svc"].get_stats_by_carbon_report_id.assert_awaited_once_with(
        carbon_report_id=1, aggregate_by="module_type_id", validated_only=True
    )


@pytest.mark.asyncio
async def test_get_validated_totals_simulator_explore_uses_validated_only_false():
    """SIMULATOR_EXPLORE report → validated_only=False."""
    db = _db()
    svcs = await _call_validated_totals(db, CarbonReportType.SIMULATOR_EXPLORE)

    svcs["emission_svc"].get_stats_by_carbon_report_id.assert_awaited_once_with(
        carbon_report_id=1, validated_only=False
    )
    svcs["fte_svc"].get_stats_by_carbon_report_id.assert_awaited_once_with(
        carbon_report_id=1, aggregate_by="module_type_id", validated_only=False
    )


@pytest.mark.asyncio
async def test_get_validated_totals_simulator_plan_uses_validated_only_true():
    """SIMULATOR_PLAN report → validated_only=True (only EXPLORE relaxes validation)."""
    db = _db()
    svcs = await _call_validated_totals(db, CarbonReportType.SIMULATOR_PLAN)

    svcs["emission_svc"].get_stats_by_carbon_report_id.assert_awaited_once_with(
        carbon_report_id=1, validated_only=True
    )


@pytest.mark.asyncio
async def test_get_validated_totals_unknown_report_id_uses_validated_only_true():
    """
    Unknown carbon_report_id (DB returns None) → validated_only=True (safe default).
    """
    db = _db()
    svcs = await _call_validated_totals(db, None)

    svcs["emission_svc"].get_stats_by_carbon_report_id.assert_awaited_once_with(
        carbon_report_id=1, validated_only=True
    )
