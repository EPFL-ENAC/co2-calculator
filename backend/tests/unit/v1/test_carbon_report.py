"""Unit tests for carbon_report API endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import app.api.v1.carbon_report as module


def _db():
    db = MagicMock()
    db.commit = AsyncMock()
    return db


def _user():
    return MagicMock()


# ── list_carbon_reports_by_unit ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_carbon_reports_by_unit_returns_list():
    db = _db()
    mock_reports = [MagicMock(), MagicMock()]
    svc = MagicMock()
    svc.list_by_unit = AsyncMock(return_value=mock_reports)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        result = await module.list_carbon_reports_by_unit(1, db, _user())
        assert result == mock_reports
    finally:
        module.CarbonReportService = original


# ── get_carbon_report_by_unit_and_year ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_carbon_report_by_unit_and_year_found():
    db = _db()
    report = MagicMock()
    svc = MagicMock()
    svc.get_by_unit_and_year = AsyncMock(return_value=report)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        result = await module.get_carbon_report_by_unit_and_year(1, 2024, db, _user())
        assert result == report
    finally:
        module.CarbonReportService = original


@pytest.mark.asyncio
async def test_get_carbon_report_by_unit_and_year_not_found():
    db = _db()
    svc = MagicMock()
    svc.get_by_unit_and_year = AsyncMock(return_value=None)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with pytest.raises(HTTPException) as exc:
            await module.get_carbon_report_by_unit_and_year(1, 2024, db, _user())
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = original


# ── create_carbon_report ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_carbon_report_commits_and_returns():
    db = _db()
    new_report = MagicMock()
    svc = MagicMock()
    svc.create = AsyncMock(return_value=new_report)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        payload = MagicMock()
        result = await module.create_carbon_report(payload, db, _user())
        assert result == new_report
        db.commit.assert_awaited_once()
    finally:
        module.CarbonReportService = original


# ── get_carbon_report ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_carbon_report_found():
    db = _db()
    report = MagicMock()
    svc = MagicMock()
    svc.get = AsyncMock(return_value=report)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        result = await module.get_carbon_report(42, db, _user())
        assert result == report
    finally:
        module.CarbonReportService = original


@pytest.mark.asyncio
async def test_get_carbon_report_not_found():
    db = _db()
    svc = MagicMock()
    svc.get = AsyncMock(return_value=None)

    original = module.CarbonReportService
    module.CarbonReportService = lambda db: svc
    try:
        with pytest.raises(HTTPException) as exc:
            await module.get_carbon_report(99, db, _user())
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = original


# ── list_carbon_report_modules ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_carbon_report_modules_found():
    db = _db()
    report = MagicMock()
    modules = [MagicMock()]
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=report)
    module_svc = MagicMock()
    module_svc.list_modules = AsyncMock(return_value=modules)

    orig_report = module.CarbonReportService
    orig_module = module.CarbonReportModuleService
    module.CarbonReportService = lambda db: report_svc
    module.CarbonReportModuleService = lambda db: module_svc
    try:
        result = await module.list_carbon_report_modules(1, db, _user())
        assert result == modules
    finally:
        module.CarbonReportService = orig_report
        module.CarbonReportModuleService = orig_module


@pytest.mark.asyncio
async def test_list_carbon_report_modules_report_not_found():
    db = _db()
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=None)

    orig_report = module.CarbonReportService
    module.CarbonReportService = lambda db: report_svc
    try:
        with pytest.raises(HTTPException) as exc:
            await module.list_carbon_report_modules(1, db, _user())
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = orig_report


# ── update_carbon_report_module_status ────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_status_success():
    db = _db()
    report = MagicMock()
    updated = MagicMock()
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=report)
    report_svc.recompute_report_progress = AsyncMock()
    module_svc = MagicMock()
    module_svc.update_status = AsyncMock(return_value=updated)

    orig_report = module.CarbonReportService
    orig_module = module.CarbonReportModuleService
    module.CarbonReportService = lambda db: report_svc
    module.CarbonReportModuleService = lambda db: module_svc
    try:
        update_payload = MagicMock()
        result = await module.update_carbon_report_module_status(
            1, 2, update_payload, db, _user()
        )
        assert result == updated
        db.commit.assert_awaited_once()
    finally:
        module.CarbonReportService = orig_report
        module.CarbonReportModuleService = orig_module


@pytest.mark.asyncio
async def test_update_status_report_not_found():
    db = _db()
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=None)

    orig_report = module.CarbonReportService
    module.CarbonReportService = lambda db: report_svc
    try:
        with pytest.raises(HTTPException) as exc:
            await module.update_carbon_report_module_status(
                1, 2, MagicMock(), db, _user()
            )
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = orig_report


@pytest.mark.asyncio
async def test_update_status_module_not_found():
    db = _db()
    report = MagicMock()
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=report)
    module_svc = MagicMock()
    module_svc.update_status = AsyncMock(return_value=None)

    orig_report = module.CarbonReportService
    orig_module = module.CarbonReportModuleService
    module.CarbonReportService = lambda db: report_svc
    module.CarbonReportModuleService = lambda db: module_svc
    try:
        with pytest.raises(HTTPException) as exc:
            await module.update_carbon_report_module_status(
                1, 2, MagicMock(), db, _user()
            )
        assert exc.value.status_code == 404
    finally:
        module.CarbonReportService = orig_report
        module.CarbonReportModuleService = orig_module


@pytest.mark.asyncio
async def test_update_status_value_error_raises_400():
    db = _db()
    report = MagicMock()
    report_svc = MagicMock()
    report_svc.get = AsyncMock(return_value=report)
    module_svc = MagicMock()
    module_svc.update_status = AsyncMock(side_effect=ValueError("bad status"))

    orig_report = module.CarbonReportService
    orig_module = module.CarbonReportModuleService
    module.CarbonReportService = lambda db: report_svc
    module.CarbonReportModuleService = lambda db: module_svc
    try:
        with pytest.raises(HTTPException) as exc:
            await module.update_carbon_report_module_status(
                1, 2, MagicMock(), db, _user()
            )
        assert exc.value.status_code == 400
        assert "bad status" in exc.value.detail
    finally:
        module.CarbonReportService = orig_report
        module.CarbonReportModuleService = orig_module
