"""#951 — data-entry permission enforcement in CarbonReportModuleWorkflow.

update(): 403 FIELD_NOT_EDITABLE on a changed field outside the row's
provenance-branch policy, value-diffed (echoed-unchanged locked fields must
not 403). delete(): 403 unless the row is user-branch. Planner rows are
exempt regardless of source.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.data_entry import DataEntrySourceEnum, DataEntryTypeEnum
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow


def _workflow_deps(existing_data: dict, source: int | None):
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    data_entry_service = MagicMock()
    data_entry_service.get = AsyncMock(
        return_value=SimpleNamespace(
            data=existing_data,
            source=source,
            data_entry_type_id=DataEntryTypeEnum.other.value,
        )
    )
    data_entry_service.update = AsyncMock(
        side_effect=lambda **kwargs: SimpleNamespace(id=kwargs["id"])
    )
    data_entry_service.delete = AsyncMock()

    emission_service = MagicMock()
    emission_service.upsert_by_data_entry = AsyncMock()
    module_service = MagicMock()
    module_service.recompute_stats = AsyncMock()

    return session, data_entry_service, emission_service, module_service


def _patched(session, data_entry_service, emission_service, module_service):
    return (
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
    )


_EXISTING_EQUIPMENT_DATA = {
    "equipment_id": "B107827",
    "name": "Freezer",
    "equipment_class": "Lab Freezer / Fridge",
    "sub_class": "Old (>=12yo)",
}
_IMPORTED_SOURCE = DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value


@pytest.mark.asyncio
async def test_update_imported_row_locked_field_changed_is_403():
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_EQUIPMENT_DATA, source=_IMPORTED_SOURCE
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        with pytest.raises(HTTPException) as exc_info:
            await workflow.update(
                carbon_report_module=SimpleNamespace(id=18036, module_type_id=4),
                data_entry_type_id=DataEntryTypeEnum.other.value,
                item_id=1,
                item_data={"equipment_class": "Something else"},
                current_user=SimpleNamespace(id=5, institutional_id="352707"),
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "FIELD_NOT_EDITABLE"
    assert "equipment_class" in exc_info.value.detail["fields"]
    data_entry_service.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_imported_row_allowed_field_changed_succeeds():
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_EQUIPMENT_DATA, source=_IMPORTED_SOURCE
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.update(
            carbon_report_module=SimpleNamespace(id=18036, module_type_id=4),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data={"sub_class": "Recent (<12yo)"},
            current_user=SimpleNamespace(id=5, institutional_id="352707"),
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_imported_row_note_always_succeeds():
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_EQUIPMENT_DATA, source=_IMPORTED_SOURCE
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.update(
            carbon_report_module=SimpleNamespace(id=18036, module_type_id=4),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data={"note": "power change requested"},
            current_user=SimpleNamespace(id=5, institutional_id="352707"),
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_imported_row_echoed_unchanged_locked_field_succeeds():
    """An edit dialog that echoes the full row back (locked field included,
    value unchanged) must not 403 — only an actual change to a locked field
    is rejected.
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_EQUIPMENT_DATA, source=_IMPORTED_SOURCE
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.update(
            carbon_report_module=SimpleNamespace(id=18036, module_type_id=4),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data={
                "equipment_class": _EXISTING_EQUIPMENT_DATA["equipment_class"],
                "sub_class": "Recent (<12yo)",
            },
            current_user=SimpleNamespace(id=5, institutional_id="352707"),
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_row_whitelisted_field_succeeds():
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_EQUIPMENT_DATA, source=None
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.update(
            carbon_report_module=SimpleNamespace(id=18036, module_type_id=4),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data={"equipment_class": "Something else"},
            current_user=SimpleNamespace(id=5, institutional_id="352707"),
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.update.assert_awaited_once()


_EXISTING_PURCHASE_DATA = {
    "name": "Lab gloves",
    "supplier": "Acme",
    "total_spent_amount": 42.0,
    "currency": "chf",
    "purchase_institutional_code": "51100000",
    "purchase_additional_code": "OLD-CODE",
}


@pytest.mark.asyncio
async def test_update_purchase_user_row_institutional_code_succeeds():
    """purchase_institutional_code resolves 'UNSPSC description' (#951) and
    is real-DTO-validated (PurchaseHandlerUpdate.validate_purchase_institutional_code)
    — this exercises the real handler, not a mock, confirming the field-diff
    check composes correctly with actual DTO validation.
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_PURCHASE_DATA, source=None
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.update(
            carbon_report_module=SimpleNamespace(id=18036, module_type_id=5),
            data_entry_type_id=DataEntryTypeEnum.services.value,
            item_id=1,
            item_data={"purchase_institutional_code": "51100001"},
            current_user=SimpleNamespace(id=5, institutional_id="352707"),
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_purchase_user_row_additional_code_is_403():
    """purchase_additional_code is NOT named in the #951 matrix — locked even
    on a user's own row.
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_PURCHASE_DATA, source=None
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        with pytest.raises(HTTPException) as exc_info:
            await workflow.update(
                carbon_report_module=SimpleNamespace(id=18036, module_type_id=5),
                data_entry_type_id=DataEntryTypeEnum.services.value,
                item_id=1,
                item_data={"purchase_additional_code": "NEW-CODE"},
                current_user=SimpleNamespace(id=5, institutional_id="352707"),
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 403
    data_entry_service.update.assert_not_called()


@pytest.mark.asyncio
async def test_delete_imported_row_is_403():
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_EQUIPMENT_DATA, source=_IMPORTED_SOURCE
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        with pytest.raises(HTTPException) as exc_info:
            await workflow.delete(
                carbon_report_module=SimpleNamespace(id=18036, module_type_id=4),
                data_entry_id=1,
                current_user=SimpleNamespace(id=5, institutional_id="352707"),
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 403
    data_entry_service.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_missing_row_is_404_not_500():
    """DataEntryService.get()/.delete() raise a bare ValueError on a missing
    row, and nothing upstream maps ValueError → 404 — without an explicit
    catch, the route's generic `except Exception` turns this into a 500.
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_EQUIPMENT_DATA, source=None
    )
    data_entry_service.get = AsyncMock(
        side_effect=ValueError("Data entry with id=1 not found")
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        with pytest.raises(HTTPException) as exc_info:
            await workflow.delete(
                carbon_report_module=SimpleNamespace(id=18036, module_type_id=4),
                data_entry_id=1,
                current_user=SimpleNamespace(id=5, institutional_id="352707"),
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 404
    data_entry_service.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_user_row_succeeds():
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_EQUIPMENT_DATA, source=None
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.delete(
            carbon_report_module=SimpleNamespace(id=18036, module_type_id=4),
            data_entry_id=1,
            current_user=SimpleNamespace(id=5, institutional_id="352707"),
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.delete.assert_awaited_once()
