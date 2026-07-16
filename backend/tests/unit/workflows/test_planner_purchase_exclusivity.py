"""Planner purchases XOR rule (PRD #1555, #1556).

A plan's Purchases module holds EITHER per-submodule CHF totals OR one
global budget — never both, and no duplicate submodule category.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.data_entry import DataEntryTypeEnum
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow


def _row(data_entry_type: DataEntryTypeEnum, data: dict) -> MagicMock:
    row = MagicMock()
    row.data_entry_type_id = data_entry_type.value
    row.data = data
    return row


def _workflow_with_rows(rows: list) -> CarbonReportModuleWorkflow:
    workflow = CarbonReportModuleWorkflow(MagicMock())
    patcher = patch(
        "app.workflows.carbon_report_module.DataEntryRepository",
        return_value=MagicMock(list_by_module=AsyncMock(return_value=rows)),
    )
    patcher.start()
    return workflow


@pytest.fixture(autouse=True)
def _stop_patches():
    yield
    patch.stopall()


@pytest.mark.asyncio
async def test_first_submodule_total_is_allowed():
    workflow = _workflow_with_rows([])
    await workflow._check_planner_purchase_exclusivity(
        1, DataEntryTypeEnum.planner_purchase, {"purchase_category": "services"}
    )


@pytest.mark.asyncio
async def test_submodule_total_rejected_when_budget_exists():
    workflow = _workflow_with_rows(
        [_row(DataEntryTypeEnum.planner_purchase_budget, {"amount_chf": 1000.0})]
    )
    with pytest.raises(HTTPException) as exc:
        await workflow._check_planner_purchase_exclusivity(
            1, DataEntryTypeEnum.planner_purchase, {"purchase_category": "services"}
        )
    assert exc.value.detail == "PURCHASES_GLOBAL_BUDGET_SET"


@pytest.mark.asyncio
async def test_duplicate_submodule_category_rejected():
    workflow = _workflow_with_rows(
        [
            _row(
                DataEntryTypeEnum.planner_purchase,
                {"purchase_category": "services", "amount_chf": 5.0},
            )
        ]
    )
    with pytest.raises(HTTPException) as exc:
        await workflow._check_planner_purchase_exclusivity(
            1, DataEntryTypeEnum.planner_purchase, {"purchase_category": "services"}
        )
    assert exc.value.detail == "DUPLICATE_PURCHASE_CATEGORY"


@pytest.mark.asyncio
async def test_budget_rejected_when_totals_exist():
    workflow = _workflow_with_rows(
        [
            _row(
                DataEntryTypeEnum.planner_purchase,
                {"purchase_category": "vehicles", "amount_chf": 5.0},
            )
        ]
    )
    with pytest.raises(HTTPException) as exc:
        await workflow._check_planner_purchase_exclusivity(
            1, DataEntryTypeEnum.planner_purchase_budget, {"amount_chf": 1000.0}
        )
    assert exc.value.detail == "PURCHASES_SUBMODULE_TOTALS_SET"


@pytest.mark.asyncio
async def test_second_budget_rejected():
    workflow = _workflow_with_rows(
        [_row(DataEntryTypeEnum.planner_purchase_budget, {"amount_chf": 1000.0})]
    )
    with pytest.raises(HTTPException) as exc:
        await workflow._check_planner_purchase_exclusivity(
            1, DataEntryTypeEnum.planner_purchase_budget, {"amount_chf": 2000.0}
        )
    assert exc.value.detail == "PURCHASES_GLOBAL_BUDGET_EXISTS"
