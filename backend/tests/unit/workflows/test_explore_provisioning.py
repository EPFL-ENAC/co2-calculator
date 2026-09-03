"""Unit tests for ExploreProvisioningWorkflow.create (#2656).

Always creates a fresh sandbox and commits — no existence check, no reuse
(that was ``ensure``, #2487, removed by #2656). Mocks ``CarbonReportService``
entirely; the aggregate-crossing create path itself (project + report +
modules) is covered in ``tests/unit/services/test_carbon_report_service.py``.
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
async def test_create_always_creates_and_commits():
    workflow, session = _workflow_with_mocked_service()
    created = MagicMock()
    workflow.report_service.create_explore = AsyncMock(return_value=created)

    result = await workflow.create(unit_id=1, created_by=10)

    assert result is created
    workflow.report_service.create_explore.assert_awaited_once_with(
        unit_id=1, created_by=10
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_never_checks_for_an_existing_sandbox():
    """No get-or-create branch left (#2656): create is the only path."""
    workflow, _ = _workflow_with_mocked_service()
    workflow.report_service.create_explore = AsyncMock(return_value=MagicMock())
    workflow.report_service.get_explore = AsyncMock()

    await workflow.create(unit_id=1, created_by=10)

    workflow.report_service.get_explore.assert_not_called()
