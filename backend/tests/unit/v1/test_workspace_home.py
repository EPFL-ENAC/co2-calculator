"""Unit tests for the workspace-home aggregate endpoint.

Focus:
- a missing carbon report 404s instead of being silently created.
- the home year configuration carries ``min_configurable_year``.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import app.api.v1.workspace_home as wh_module


def _db(module_state_rows=None):
    db = MagicMock()
    db.commit = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock())  # unit lookup
    result = MagicMock()
    result.all.return_value = module_state_rows or [(1, 2)]
    db.execute = AsyncMock(return_value=result)
    return db


def _report(report_id: int = 42):
    return SimpleNamespace(
        id=report_id,
        unit_id=1,
        year=2025,
        carbon_project_id=1,
        stats={"buckets": {}, "total": 41000.0, "total_fte": 3.0},
    )


def _patch_common(monkeypatch, *, existing_report):
    """Stub every collaborator; return the mock report service for assertions."""
    report_service = MagicMock()
    report_service.get_by_unit_and_year = AsyncMock(return_value=existing_report)
    report_service.create = AsyncMock(return_value=_report())

    monkeypatch.setattr(wh_module, "require_unit_access", MagicMock())
    monkeypatch.setattr(wh_module, "CarbonReportService", lambda _db: report_service)
    monkeypatch.setattr(
        wh_module,
        "build_home_year_configuration",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        wh_module,
        "build_validated_totals",
        AsyncMock(return_value={"total_tonnes_co2eq": 6.1, "total_fte": 3.0}),
    )
    return report_service


@pytest.mark.asyncio
async def test_missing_report_returns_404(monkeypatch):
    db = _db()
    report_service = _patch_common(monkeypatch, existing_report=None)

    with pytest.raises(HTTPException) as exc_info:
        await wh_module.get_workspace_home(
            unit_id=1, year=2025, db=db, current_user=MagicMock()
        )

    assert exc_info.value.status_code == 404
    report_service.create.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_home_year_config_carries_min_configurable_year():
    # Regression: the workspace guard fans this slim payload into the frontend
    # yearConfig store, which hard-errors on any year-config response missing
    # ``min_configurable_year`` (#1204 follow-up).
    db = MagicMock()
    result = MagicMock()
    result.first.return_value = SimpleNamespace(year=2025, config={"modules": {}})
    db.exec = AsyncMock(return_value=result)

    config = await wh_module.build_home_year_configuration(db, 2025, MagicMock())

    assert config is not None
    assert config.min_configurable_year == wh_module.settings.MIN_CONFIGURABLE_YEAR
