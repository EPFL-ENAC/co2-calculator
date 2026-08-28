"""Unit tests for ExploreProvisioningWorkflow.ensure (#2487).

The PUT route's "does this exist" decision: create on first call, return
the existing sandbox on every call after — no 404, no client-orchestrated
race. Mocks ``CarbonReportService`` entirely; the aggregate-crossing create
path itself (project + report + modules, and the #2483 SAVEPOINT guards)
is covered in ``tests/unit/services/test_carbon_report_service.py``.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workflows.explore_provisioning import ExploreProvisioningWorkflow


def _workflow_with_mocked_service():
    session = MagicMock()
    session.commit = AsyncMock()
    workflow = ExploreProvisioningWorkflow(session)
    workflow.report_service = MagicMock()
    return workflow, session


@pytest.mark.asyncio
async def test_ensure_returns_existing_without_creating_or_committing():
    workflow, session = _workflow_with_mocked_service()
    existing = MagicMock()
    workflow.report_service.get_explore = AsyncMock(return_value=existing)
    workflow.report_service.create_explore = AsyncMock()

    result = await workflow.ensure(unit_id=1, reference_year=2024, created_by=10)

    assert result is existing
    workflow.report_service.create_explore.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_creates_and_commits_when_missing():
    workflow, session = _workflow_with_mocked_service()
    created = MagicMock()
    workflow.report_service.get_explore = AsyncMock(return_value=None)
    workflow.report_service.create_explore = AsyncMock(return_value=created)

    result = await workflow.ensure(unit_id=1, reference_year=2024, created_by=10)

    assert result is created
    workflow.report_service.create_explore.assert_awaited_once_with(
        unit_id=1, reference_year=2024, created_by=10
    )
    session.commit.assert_awaited_once()
