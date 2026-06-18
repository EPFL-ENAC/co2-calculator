"""Regression tests for CarbonReportModuleWorkflow.update payload assembly."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow


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
    data_entry_service.get = AsyncMock(return_value=SimpleNamespace(data=existing_data))

    async def _capture_update(*, id, data, user, request_context, background_tasks):
        captured["data"] = data
        return SimpleNamespace(id=id)

    data_entry_service.update = AsyncMock(side_effect=_capture_update)

    # resolve echoes its payload back — the merge under test happens BEFORE this
    # call, so an echo faithfully exposes what validation will receive.
    factor = SimpleNamespace(id=1998, values={})

    async def _echo_resolve(handler, payload, *args, **kwargs):
        return payload, factor

    handler_service = MagicMock()
    handler_service.resolve_primary_factor_if_changed = AsyncMock(
        side_effect=_echo_resolve
    )

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
            "app.workflows.carbon_report_module.ModuleHandlerService",
            return_value=handler_service,
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
            carbon_report_module=SimpleNamespace(id=18036, module_type_id=4),
            data_entry_type_id=DataEntryTypeEnum.other.value,
            item_id=1,
            item_data=item_data,
            current_user=SimpleNamespace(id=5, institutional_id="352707"),
            request_context={},
            background_tasks=MagicMock(),
            year=2025,
        )

    persisted = captured["data"].data
    assert persisted["equipment_class"] == "Lab Freezer / Frigde"
    assert persisted["sub_class"] == "Recent -80C freezers (<12yo)"
