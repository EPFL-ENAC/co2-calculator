"""Regression tests for CarbonReportModuleWorkflow.create — issue #1564.

A member can legitimately hold two roles (different ``sius_code``) in the
same unit. The uniqueness check on manual (API) create must key on
``(user_institutional_id, sius_code)``, not ``user_institutional_id`` alone.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.data_entry import DataEntrySourceEnum, DataEntryTypeEnum
from app.models.user import UserProvider
from app.schemas.data_entry import DataEntryResponse
from app.schemas.user import UserRead
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow

_CURRENT_USER = UserRead(
    id=5,
    display_name="Test User",
    email="test.user@example.org",
    provider=UserProvider.TEST,
    institutional_id="352707",
)


def _member_item_data(sius_code: str) -> dict:
    return {
        "name": "X X",
        "user_institutional_id": "123456",
        "sius_code": sius_code,
        "fte": 0.5,
    }


def _make_workflow_deps():
    """Build the mocked DataEntryService/EmissionService/ModuleService trio
    shared by both tests, mirroring the pattern in
    test_carbon_report_module_update.py.
    """
    session = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    data_entry_service = MagicMock()
    data_entry_service.create = AsyncMock(
        return_value=DataEntryResponse(
            id=1,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=42,
            data=_member_item_data("54"),
        )
    )

    emission_service = MagicMock()
    # #2050 J4: the create path calls ``create`` (no pre-delete lookup to
    # waste); the update path still calls ``upsert_by_data_entry``.
    emission_service.create = AsyncMock()
    emission_service.upsert_by_data_entry = AsyncMock()
    module_service = MagicMock()
    module_service.recompute_stats = AsyncMock()

    return session, data_entry_service, emission_service, module_service


@pytest.mark.asyncio
async def test_create_second_role_for_existing_member_is_accepted():
    """A second role (different sius_code) for an already-registered SCIPER
    in the same unit must succeed (201), not be rejected as a duplicate.
    """
    session, data_entry_service, emission_service, module_service = (
        _make_workflow_deps()
    )
    workflow = CarbonReportModuleWorkflow(session)

    with (
        patch(
            "app.workflows.carbon_report_module.DataEntryService",
            return_value=data_entry_service,
        ),
        patch(
            "app.workflows.carbon_report_module.DataEntryEmissionService",
            return_value=emission_service,
        ),
        patch(
            "app.workflows.carbon_report_module.CarbonReportModuleService",
            return_value=module_service,
        ),
    ):
        response = await workflow.create(
            carbon_report_module=MagicMock(id=42, module_type_id=1),
            data_entry_type_id=DataEntryTypeEnum.member.value,
            item_data=_member_item_data("54"),
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    assert response.id == 1
    # #2050 J4: no uniqueness pre-check any more — uq_member_role_per_module
    # enforces it, and a second role for the same person is outside the key.
    data_entry_service.check_member_role_unique.assert_not_called()
    data_entry_service.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_duplicate_role_for_existing_member_is_rejected():
    """The same (user_institutional_id, sius_code) pair must still be
    rejected with 422 DUPLICATE_INSTITUTIONAL_ID.
    """
    session, data_entry_service, emission_service, module_service = (
        _make_workflow_deps()
    )
    # #2050 J4: the duplicate now surfaces from the unique index rather than
    # from a pre-check, so the insert is what raises.
    data_entry_service.create = AsyncMock(
        side_effect=IntegrityError(
            "INSERT INTO data_entries ...",
            {},
            Exception(
                "duplicate key value violates unique constraint "
                '"uq_member_role_per_module"'
            ),
        )
    )
    workflow = CarbonReportModuleWorkflow(session)

    with (
        patch(
            "app.workflows.carbon_report_module.DataEntryService",
            return_value=data_entry_service,
        ),
        patch(
            "app.workflows.carbon_report_module.DataEntryEmissionService",
            return_value=emission_service,
        ),
        patch(
            "app.workflows.carbon_report_module.CarbonReportModuleService",
            return_value=module_service,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await workflow.create(
                carbon_report_module=MagicMock(id=42, module_type_id=1),
                data_entry_type_id=DataEntryTypeEnum.member.value,
                item_data=_member_item_data("53"),
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "DUPLICATE_INSTITUTIONAL_ID"
    session.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_create_stamps_source_manual_and_created_by_id():
    """Manual creates must stamp source=USER_MANUAL and created_by_id —
    #951: without this, manual rows are indistinguishable from imported rows
    with source=NULL, and data-entry permission enforcement can't tell them
    apart.
    """
    session, data_entry_service, emission_service, module_service = (
        _make_workflow_deps()
    )
    data_entry_service.check_member_role_unique = AsyncMock(return_value=True)
    workflow = CarbonReportModuleWorkflow(session)

    with (
        patch(
            "app.workflows.carbon_report_module.DataEntryService",
            return_value=data_entry_service,
        ),
        patch(
            "app.workflows.carbon_report_module.DataEntryEmissionService",
            return_value=emission_service,
        ),
        patch(
            "app.workflows.carbon_report_module.CarbonReportModuleService",
            return_value=module_service,
        ),
    ):
        await workflow.create(
            carbon_report_module=MagicMock(id=42, module_type_id=1),
            data_entry_type_id=DataEntryTypeEnum.member.value,
            item_data=_member_item_data("54"),
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    call_kwargs = data_entry_service.create.call_args.kwargs
    assert call_kwargs["source"] == DataEntrySourceEnum.USER_MANUAL.value
    assert call_kwargs["created_by_id"] == _CURRENT_USER.id
