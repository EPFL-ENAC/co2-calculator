"""Regression tests for CarbonReportModuleWorkflow.update payload assembly."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.data_entry import DataEntryTypeEnum
from app.models.user import UserProvider
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow

_CURRENT_USER = SimpleNamespace(
    id=5, institutional_id="352707", provider=UserProvider.TEST
)


def _stub_inputs_deactivated_lookup(session: MagicMock) -> None:
    """#2007 guard: resolve the report, then look up its year config.

    No ``year_configuration`` row → not deactivated, the schema default.
    """
    session.get = AsyncMock(
        return_value=SimpleNamespace(year=2026, carbon_project_id=None)
    )
    no_year_config = MagicMock()
    no_year_config.first = MagicMock(return_value=None)
    session.exec = AsyncMock(return_value=no_year_config)


@pytest.mark.asyncio
async def test_update_partial_patch_retains_persisted_classification():
    """A partial PATCH that changes only ``sub_class`` must not drop the
    persisted ``equipment_class``.

    Regression: ``update_payload`` was built from the incoming PATCH alone, so
    the kind field (``equipment_class``) never reached validation and the
    validated entry came back with ``equipment_class=None`` — corrupting the
    data fed to factor resolution and emission recompute.
    """
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    _stub_inputs_deactivated_lookup(session)
    workflow = CarbonReportModuleWorkflow(session)

    existing_data = {
        "equipment_id": "B107827",
        "name": "Freezer",
        "equipment_class": "Lab Freezer / Frigde",
        "status": 1,
        "primary_factor_id": None,
    }
    # PATCH changes the sub_class only — equipment_class is NOT resent.
    item_data = {"sub_class": "Recent -80C freezers (<12yo)"}

    captured: dict = {}

    data_entry_service = MagicMock()
    data_entry_service.get = AsyncMock(
        return_value=SimpleNamespace(data=existing_data, source=None)
    )

    async def _capture_update(*, id, data, user, request_context, background_tasks):
        captured["data"] = data
        return SimpleNamespace(id=id)

    data_entry_service.update = AsyncMock(side_effect=_capture_update)

    # clear_dependent_fields_on_kind_change is a pure staticmethod — the
    # real one runs; the merge under test happens before validation.
    emission_service = MagicMock()
    emission_service.upsert_by_data_entry = AsyncMock()
    module_service = MagicMock()
    module_service.recompute_stats = AsyncMock()

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
        await workflow.update(
            carbon_report_module=SimpleNamespace(
                id=18036, carbon_report_id=99, module_type_id=4
            ),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data=item_data,
            current_user=_CURRENT_USER,
            request_context={},
            background_tasks=MagicMock(),
        )

    persisted = captured["data"].data
    assert persisted["equipment_class"] == "Lab Freezer / Frigde"
    assert persisted["sub_class"] == "Recent -80C freezers (<12yo)"


@pytest.mark.asyncio
async def test_update_blank_purchase_institutional_code_rejected():
    """A PATCH clearing ``purchase_institutional_code`` to "" must fail loudly
    at validation, not persist a blank code with no resolvable factor.

    Regression: the old resolver raised ValueError on a falsy kind, which this
    workflow wraps into HTTP 400. The new resolver returns None for a missing
    kind (correct recalc semantics), so without DTO-level rejection the blank
    code would silently persist and the entry would lose its emission.
    """
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    _stub_inputs_deactivated_lookup(session)
    workflow = CarbonReportModuleWorkflow(session)

    existing_data = {
        "name": "Widget",
        "total_spent_amount": 100.0,
        "purchase_institutional_code": "51100000",
    }
    item_data = {"purchase_institutional_code": ""}

    data_entry_service = MagicMock()
    data_entry_service.get = AsyncMock(
        return_value=SimpleNamespace(data=existing_data, source=None)
    )
    data_entry_service.update = AsyncMock()

    # clearing is a pure staticmethod (real); validation (real, unmocked)
    # is what must reject the blank code.
    emission_service = MagicMock()
    emission_service.upsert_by_data_entry = AsyncMock()
    module_service = MagicMock()
    module_service.recompute_stats = AsyncMock()

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
            await workflow.update(
                carbon_report_module=SimpleNamespace(
                    id=18036, carbon_report_id=99, module_type_id=4
                ),
                data_entry_type_id=DataEntryTypeEnum.it_equipment.value,
                item_id=1,
                item_data=item_data,
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 400
    data_entry_service.update.assert_not_called()
    emission_service.upsert_by_data_entry.assert_not_called()


@pytest.mark.asyncio
async def test_update_value_error_from_emission_service_returns_422():
    """A #2050 J1 fail-hard ValueError from emission recompute must surface
    as 422 with its own message, not a generic 500 — matches create()'s
    equivalent regression test.
    """
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    _stub_inputs_deactivated_lookup(session)
    workflow = CarbonReportModuleWorkflow(session)

    # Same existing_data/item_data/module type as
    # test_update_partial_patch_retains_persisted_classification, which is
    # already known to clear the field-permission gate — this test only
    # needs to reach the write step below it.
    existing_data = {
        "equipment_id": "B107827",
        "name": "Freezer",
        "equipment_class": "Lab Freezer / Frigde",
        "status": 1,
        "primary_factor_id": None,
    }
    item_data = {"sub_class": "Recent -80C freezers (<12yo)"}

    data_entry_service = MagicMock()
    data_entry_service.get = AsyncMock(
        return_value=SimpleNamespace(data=existing_data, source=None)
    )
    data_entry_service.update = AsyncMock(return_value=SimpleNamespace(id=1))

    emission_service = MagicMock()
    emission_service.upsert_by_data_entry = AsyncMock(
        side_effect=ValueError("factor_id=37756: could not produce a value.")
    )
    module_service = MagicMock()
    module_service.recompute_stats = AsyncMock()

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
            await workflow.update(
                carbon_report_module=SimpleNamespace(
                    id=18036, carbon_report_id=99, module_type_id=4
                ),
                data_entry_type_id=DataEntryTypeEnum.other.value,
                item_id=1,
                item_data=item_data,
                current_user=_CURRENT_USER,
                request_context={},
                background_tasks=MagicMock(),
            )

    assert exc_info.value.status_code == 422
    assert "factor_id=37756" in exc_info.value.detail
    session.rollback.assert_awaited()
