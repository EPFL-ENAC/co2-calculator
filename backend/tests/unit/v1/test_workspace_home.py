"""Unit tests for the workspace-home aggregate endpoint.

Focus:
- get-or-create: a missing carbon report is created (and committed) server-side.
- the emission breakdown is always returned, augmented with the validated-only
  ``total_tonnes_validated_co2eq`` (semantics delegated to build_validated_totals).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.api.v1.workspace_home as wh_module


def _db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock())  # unit lookup
    return db


def _report(report_id: int = 42):
    return SimpleNamespace(id=report_id, unit_id=1, year=2025, carbon_project_id=1)


def _patch_common(monkeypatch, *, existing_report):
    """Stub every collaborator; return the mock report service for assertions."""
    report_service = MagicMock()
    report_service.get_by_unit_and_year = AsyncMock(return_value=existing_report)
    report_service.create = AsyncMock(return_value=_report())

    monkeypatch.setattr(wh_module, "require_unit_access", MagicMock())
    monkeypatch.setattr(wh_module, "CarbonReportService", lambda _db: report_service)
    monkeypatch.setattr(
        wh_module,
        "build_year_configuration_response",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        wh_module,
        "build_emission_breakdown",
        AsyncMock(
            return_value={
                "module_breakdown": [],
                "total_tonnes_co2eq": 41.0,
                # Per-module states now ride inside the breakdown.
                "module_states": [{"module_type_id": 1, "status": 2}],
            }
        ),
    )
    monkeypatch.setattr(
        wh_module,
        "build_validated_totals",
        AsyncMock(return_value={"total_tonnes_co2eq": 6.1, "total_fte": 3.0}),
    )
    return report_service


@pytest.mark.asyncio
async def test_get_or_create_report_when_missing(monkeypatch):
    db = _db()
    report_service = _patch_common(monkeypatch, existing_report=None)

    result = await wh_module.get_workspace_home(
        unit_id=1, year=2025, db=db, current_user=MagicMock()
    )

    report_service.create.assert_awaited_once()
    db.commit.assert_awaited_once()
    assert result.carbon_report_id == 42


@pytest.mark.asyncio
async def test_existing_report_is_not_recreated(monkeypatch):
    db = _db()
    report_service = _patch_common(monkeypatch, existing_report=_report(7))

    result = await wh_module.get_workspace_home(
        unit_id=1, year=2025, db=db, current_user=MagicMock()
    )

    report_service.create.assert_not_awaited()
    db.commit.assert_not_awaited()
    assert result.carbon_report_id == 7


@pytest.mark.asyncio
async def test_breakdown_always_present_with_validated_total(monkeypatch):
    db = _db()
    _patch_common(monkeypatch, existing_report=_report())

    result = await wh_module.get_workspace_home(
        unit_id=1, year=2025, db=db, current_user=MagicMock()
    )

    # The all-modules total stays untouched; the validated-only total is merged
    # in from build_validated_totals.
    assert result.emission_breakdown["total_tonnes_co2eq"] == 41.0
    assert result.emission_breakdown["total_tonnes_validated_co2eq"] == 6.1
    # Per-module states are passed through inside the breakdown (no separate
    # top-level field / list_modules call).
    assert result.emission_breakdown["module_states"] == [
        {"module_type_id": 1, "status": 2}
    ]
    wh_module.build_emission_breakdown.assert_awaited_once()
    wh_module.build_validated_totals.assert_awaited_once()
