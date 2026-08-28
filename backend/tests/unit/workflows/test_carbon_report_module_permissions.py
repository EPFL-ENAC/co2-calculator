"""#951 — data-entry permission enforcement in CarbonReportModuleWorkflow.

update(): 403 FIELD_NOT_EDITABLE on a changed field outside the row's
provenance-branch policy, value-diffed (echoed-unchanged locked fields must
not 403). delete(): 403 unless the row is user-branch. Planner-kind types
are exempt regardless of source; planner snapshot rows are user-branch and
additionally own percentage_of_reference_year (#2176).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.data_entry import DataEntrySourceEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import UserProvider
from app.schemas.data_entry import DataEntryResponse
from app.schemas.user import UserRead
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow

_CURRENT_USER = SimpleNamespace(
    id=5, institutional_id="352707", provider=UserProvider.TEST
)
# The create path revalidates the acting user through UserRead; update and
# delete only read attributes off it.
_CURRENT_USER_READ = UserRead(
    id=5,
    display_name="Test User",
    email="test.user@example.org",
    provider=UserProvider.TEST,
    institutional_id="352707",
)


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
    data_entry_service.create = AsyncMock(
        return_value=DataEntryResponse(
            id=1,
            data_entry_type_id=DataEntryTypeEnum.research_facilities.value,
            carbon_report_module_id=18036,
            data={},
        )
    )

    # #2007: the inputs-deactivated guard resolves the report, then its year
    # config. No year_configuration row → not deactivated, the schema default.
    session.get = AsyncMock(
        return_value=SimpleNamespace(year=2026, carbon_project_id=None)
    )
    no_year_config = MagicMock()
    no_year_config.first = MagicMock(return_value=None)
    session.exec = AsyncMock(return_value=no_year_config)

    emission_service = MagicMock()
    emission_service.upsert_by_data_entry = AsyncMock()
    emission_service.create = AsyncMock()
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
# #2453: a CSV uploaded INTO ONE'S OWN module (job config carries
# carbon_report_module_id) is the operator's own data — user branch.
_UNIT_SPECIFIC_SOURCE = DataEntrySourceEnum.CSV_MODULE_UNIT_SPECIFIC.value


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
                carbon_report_module=SimpleNamespace(
                    id=18036, carbon_report_id=99, module_type_id=4
                ),
                data_entry_type_id=DataEntryTypeEnum.other.value,
                item_id=1,
                item_data={"equipment_class": "Something else"},
                current_user=_CURRENT_USER,
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
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=4
            ),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data={"sub_class": "Recent (<12yo)"},
            current_user=_CURRENT_USER,
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
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=4
            ),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data={"note": "power change requested"},
            current_user=_CURRENT_USER,
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
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=4
            ),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data={
                "equipment_class": _EXISTING_EQUIPMENT_DATA["equipment_class"],
                "sub_class": "Recent (<12yo)",
            },
            current_user=_CURRENT_USER,
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
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=4
            ),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data={"equipment_class": "Something else"},
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_planner_snapshot_row_percentage_succeeds():
    """The planner slider PATCHes percentage_of_reference_year, a field in no
    module whitelist — a PLANNER_SNAPSHOT row must accept it (#2176).
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        {**_EXISTING_EQUIPMENT_DATA, "percentage_of_reference_year": 100},
        source=DataEntrySourceEnum.PLANNER_SNAPSHOT.value,
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.update(
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=4
            ),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data={"percentage_of_reference_year": 50},
            current_user=_CURRENT_USER,
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
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=5
            ),
            data_entry_type_id=DataEntryTypeEnum.services.value,
            item_id=1,
            item_data={"purchase_institutional_code": "51100001"},
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_purchase_kind_change_clears_locked_dependent_field():
    """Pinned behavior (code review 2026-08-13, product decision: allow):
    changing purchase_institutional_code (the handler's kind_field, allowed
    on a user row) triggers clear_dependent_fields_on_kind_change() to null
    purchase_additional_code (kind_field_override, #951-locked) as a
    data-integrity cascade — the stale secondary code no longer applies to
    the new classification. This is intentionally NOT checked as a locked-
    field violation: the user never submitted purchase_additional_code
    themselves, the system is invalidating a now-stale dependent value as a
    consequence of an edit they ARE authorized to make. If this behavior
    ever needs to change (e.g. block the update instead), this test is the
    one to update alongside the workflow comment explaining the decision.
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_PURCHASE_DATA, source=None
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.update(
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=5
            ),
            data_entry_type_id=DataEntryTypeEnum.services.value,
            item_id=1,
            item_data={"purchase_institutional_code": "51100001"},
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    persisted = data_entry_service.update.call_args.kwargs["data"].data
    assert persisted["purchase_institutional_code"] == "51100001"
    assert persisted["purchase_additional_code"] is None


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
                carbon_report_module=SimpleNamespace(
                    id=18036, carbon_report_id=99, module_type_id=5
                ),
                data_entry_type_id=DataEntryTypeEnum.services.value,
                item_id=1,
                item_data={"purchase_additional_code": "NEW-CODE"},
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 403
    data_entry_service.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_unit_specific_upload_row_succeeds():
    """#2453 regression: rows a user CSV-uploaded into their own module were
    403 FIELD_NOT_EDITABLE on every field — ``equipment_class`` is outside
    the IMPORTED whitelist but inside the USER one, so it is the field that
    discriminates the two branches.
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_EQUIPMENT_DATA, source=_UNIT_SPECIFIC_SOURCE
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.update(
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=4
            ),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data={"equipment_class": "Something else"},
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.update.assert_called_once()


@pytest.mark.asyncio
async def test_delete_unit_specific_upload_row_succeeds():
    """#2453 regression: the same rows were 403 ROW_NOT_DELETABLE."""
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_EQUIPMENT_DATA, source=_UNIT_SPECIFIC_SOURCE
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.delete(
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=4
            ),
            data_entry_id=1,
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.delete.assert_called_once()


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
                carbon_report_module=SimpleNamespace(
                    id=18036, carbon_report_id=99, module_type_id=4
                ),
                data_entry_id=1,
                current_user=_CURRENT_USER,
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
                carbon_report_module=SimpleNamespace(
                    id=18036, carbon_report_id=99, module_type_id=4
                ),
                data_entry_id=1,
                current_user=_CURRENT_USER,
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
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=4
            ),
            data_entry_id=1,
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.delete.assert_awaited_once()


_EXISTING_MEMBER_DATA = {
    "name": "Test Member",
    "sius_code": "54",
    "user_institutional_id": "123456",
    "fte": 0.8,
}


@pytest.mark.asyncio
async def test_update_member_sciper_on_user_row_succeeds_when_unique():
    """#951: SCIPER (user_institutional_id) is updatable on a user's own
    headcount row (product decision 2026-08-13). Mirrors create()'s
    (uid, sius_code) uniqueness check, now needed on update too since the
    field wasn't writable before this change.
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_MEMBER_DATA, source=None
    )
    data_entry_service.check_member_role_unique = AsyncMock(return_value=True)
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.update(
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=1
            ),
            data_entry_type_id=DataEntryTypeEnum.member.value,
            item_id=1,
            item_data={"user_institutional_id": "654321"},
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.check_member_role_unique.assert_awaited_once()
    call_kwargs = data_entry_service.check_member_role_unique.call_args.kwargs
    assert call_kwargs["uid"] == "654321"
    assert call_kwargs["sius_code"] == "54"
    assert call_kwargs["exclude_id"] == 1
    data_entry_service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_member_sciper_duplicate_is_rejected():
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_MEMBER_DATA, source=None
    )
    data_entry_service.check_member_role_unique = AsyncMock(return_value=False)
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        with pytest.raises(HTTPException) as exc_info:
            await workflow.update(
                carbon_report_module=SimpleNamespace(
                    id=18036, carbon_report_id=99, module_type_id=1
                ),
                data_entry_type_id=DataEntryTypeEnum.member.value,
                item_id=1,
                item_data={"user_institutional_id": "999999"},
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "DUPLICATE_INSTITUTIONAL_ID"
    data_entry_service.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_member_sciper_on_imported_row_is_403():
    """Locked on an imported row — the whole point of gating it by
    provenance rather than just adding it to the DTO.
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        _EXISTING_MEMBER_DATA, source=_IMPORTED_SOURCE
    )
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        with pytest.raises(HTTPException) as exc_info:
            await workflow.update(
                carbon_report_module=SimpleNamespace(
                    id=18036, carbon_report_id=99, module_type_id=1
                ),
                data_entry_type_id=DataEntryTypeEnum.member.value,
                item_id=1,
                item_data={"user_institutional_id": "654321"},
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "FIELD_NOT_EDITABLE"
    data_entry_service.update.assert_not_called()


# ── #2007: the backoffice "deactivate inputs" switch fails closed ────────────
# It used to hide the form and nothing more, so a raw API client could still
# write to a submodule the backoffice had switched off.


def _deactivated(session, *, carbon_project_id=None):
    """Point the workflow at a year config with RF inputs deactivated."""
    session.get = AsyncMock(
        return_value=SimpleNamespace(year=2026, carbon_project_id=carbon_project_id)
    )
    year_config = SimpleNamespace(
        config={
            "modules": {
                str(ModuleTypeEnum.research_facilities.value): {
                    "submodules": {
                        str(DataEntryTypeEnum.research_facilities.value): {
                            "inputs_deactivated": True
                        }
                    }
                }
            }
        }
    )
    result = MagicMock()
    result.first = MagicMock(return_value=year_config)
    session.exec = AsyncMock(return_value=result)


_RF_MODULE = SimpleNamespace(
    id=18036,
    carbon_report_id=99,
    module_type_id=ModuleTypeEnum.research_facilities.value,
)
_RF_TYPE = DataEntryTypeEnum.research_facilities.value


@pytest.mark.asyncio
async def test_create_is_403_when_inputs_deactivated():
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        {}, source=DataEntrySourceEnum.USER_MANUAL.value
    )
    _deactivated(session)
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        with pytest.raises(HTTPException) as exc_info:
            await workflow.create(
                carbon_report_module=_RF_MODULE,
                data_entry_type_id=_RF_TYPE,
                item_data={
                    "researchfacility_id": "1902",
                    "researchfacility_name": "SCITAS-GE",
                    "use": 1000,
                    "use_unit": "CHF",
                },
                current_user=_CURRENT_USER_READ,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "INPUTS_DEACTIVATED"
    data_entry_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_delete_is_403_when_inputs_deactivated():
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        {}, source=DataEntrySourceEnum.USER_MANUAL.value
    )
    data_entry_service.get = AsyncMock(
        return_value=SimpleNamespace(
            data={},
            source=DataEntrySourceEnum.USER_MANUAL.value,
            data_entry_type_id=_RF_TYPE,
        )
    )
    _deactivated(session)
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        with pytest.raises(HTTPException) as exc_info:
            await workflow.delete(
                carbon_report_module=_RF_MODULE,
                data_entry_id=1,
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.detail["code"] == "INPUTS_DEACTIVATED"
    data_entry_service.delete.assert_not_called()


@pytest.mark.asyncio
async def test_update_note_still_saves_when_inputs_deactivated():
    """Annotation is not data entry — a note stays writable on a closed
    submodule, the same exemption #951 gives it everywhere else.
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        {"researchfacility_id": "1902", "use": 1000},
        source=DataEntrySourceEnum.USER_MANUAL.value,
    )
    data_entry_service.get = AsyncMock(
        return_value=SimpleNamespace(
            data={"researchfacility_id": "1902", "use": 1000},
            source=DataEntrySourceEnum.USER_MANUAL.value,
            data_entry_type_id=_RF_TYPE,
        )
    )
    _deactivated(session)
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.update(
            carbon_report_module=_RF_MODULE,
            data_entry_type_id=_RF_TYPE,
            item_id=1,
            item_data={"note": "counted manually"},
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_on_plan_report_ignores_inputs_deactivated():
    """A plan/grant report carries the user's own scenario, not calculator
    data entry — the Project Grant research-facilities grid must keep working
    while the calculator switch is off.
    """
    session, data_entry_service, emission_service, module_service = _workflow_deps(
        {}, source=DataEntrySourceEnum.USER_MANUAL.value
    )
    _deactivated(session, carbon_project_id=7)
    p1, p2, p3 = _patched(session, data_entry_service, emission_service, module_service)
    workflow = CarbonReportModuleWorkflow(session)

    with p1, p2, p3:
        await workflow.create(
            carbon_report_module=_RF_MODULE,
            data_entry_type_id=_RF_TYPE,
            item_data={
                "researchfacility_id": "1902",
                "researchfacility_name": "SCITAS-GE",
                "use": 1000,
                "use_unit": "CHF",
            },
            current_user=_CURRENT_USER_READ,
            request_context={},
            background_tasks=MagicMock(),
        )

    data_entry_service.create.assert_awaited_once()
