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


@pytest.mark.asyncio
async def test_create_value_error_from_emission_service_returns_422():
    """A #2050 J1 fail-hard ValueError (e.g. a formula that can't produce a
    value) must surface as 422 with its own message, not a generic 500 —
    regression for the bare "Failed to create data entry" response that gave
    no clue which factor/entry was the problem.
    """
    session, data_entry_service, emission_service, module_service = (
        _make_workflow_deps()
    )
    emission_service.create = AsyncMock(
        side_effect=ValueError(
            "data_entry_id=9237, emission_type='research_facilities__facilities', "
            "factor_id=37756: The formula for "
            "'research_facilities__facilities' could not produce a value."
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
                carbon_report_module=MagicMock(id=42, module_type_id=6),
                data_entry_type_id=DataEntryTypeEnum.member.value,
                item_data=_member_item_data("54"),
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 422
    assert "factor_id=37756" in exc_info.value.detail
    session.rollback.assert_awaited()


def _train_item_data(**overrides: object) -> dict:
    base = {
        "user_institutional_id": "123456",
        "origin_name": "Geneva",
        "destination_name": "Lausanne",
        "origin_country_code": "CH",
        "destination_country_code": "CH",
        "origin_natural_key": "train:ch:geneva:46.2104:6.1428",
        "destination_natural_key": "train:ch:lausanne:46.5197:6.6323",
        "cabin_class": "second",
        "number_of_trips": 1,
    }
    return {**base, **overrides}


@pytest.mark.asyncio
async def test_create_train_without_natural_key_is_rejected():
    """#1186: origin_natural_key/destination_natural_key stay optional on
    the DTO (CSV rows validate before enrich_csv_row resolves them), so a
    train API create missing them must be rejected here — not left to
    silently zero-emission at recalc time.
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
        with pytest.raises(HTTPException) as exc_info:
            await workflow.create(
                carbon_report_module=MagicMock(id=42, module_type_id=1),
                data_entry_type_id=DataEntryTypeEnum.train.value,
                item_data=_train_item_data(origin_natural_key=None),
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "TRAIN_STATION_NOT_RESOLVED"
    data_entry_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_train_with_natural_key_omitted_is_rejected():
    """The real client shape: ``buildPayload`` never sends an ``undefined``
    key at all (JSON drops it), so the omitted-key case — not just an
    explicit ``None`` — must hit the same guard.
    """
    session, data_entry_service, emission_service, module_service = (
        _make_workflow_deps()
    )
    workflow = CarbonReportModuleWorkflow(session)
    item_data = {
        k: v for k, v in _train_item_data().items() if k != "origin_natural_key"
    }

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
                data_entry_type_id=DataEntryTypeEnum.train.value,
                item_data=item_data,
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "TRAIN_STATION_NOT_RESOLVED"
    data_entry_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_train_with_natural_key_succeeds():
    session, data_entry_service, emission_service, module_service = (
        _make_workflow_deps()
    )
    data_entry_service.create = AsyncMock(
        return_value=DataEntryResponse(
            id=7,
            data_entry_type_id=DataEntryTypeEnum.train.value,
            carbon_report_module_id=42,
            data=_train_item_data(),
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
        response = await workflow.create(
            carbon_report_module=MagicMock(id=42, module_type_id=1),
            data_entry_type_id=DataEntryTypeEnum.train.value,
            item_data=_train_item_data(),
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    assert response.id == 7
    data_entry_service.create.assert_awaited_once()
