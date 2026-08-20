"""Planner purchases XOR rule (PRD #1555, #1556).

A plan's Purchases module holds EITHER per-submodule EUR totals OR one
global budget — never both, and no duplicate submodule category.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.data_entry import DataEntryTypeEnum
from app.workflows.carbon_report_module import CarbonReportModuleWorkflow


def _row(data_entry_type: DataEntryTypeEnum, data: dict, row_id: int = 1) -> MagicMock:
    row = MagicMock()
    row.id = row_id
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
        [_row(DataEntryTypeEnum.planner_purchase_budget, {"amount_eur": 1000.0})]
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
                {"purchase_category": "services", "amount_eur": 5.0},
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
                {"purchase_category": "vehicles", "amount_eur": 5.0},
            )
        ]
    )
    with pytest.raises(HTTPException) as exc:
        await workflow._check_planner_purchase_exclusivity(
            1, DataEntryTypeEnum.planner_purchase_budget, {"amount_eur": 1000.0}
        )
    assert exc.value.detail == "PURCHASES_SUBMODULE_TOTALS_SET"


@pytest.mark.asyncio
async def test_second_budget_rejected():
    workflow = _workflow_with_rows(
        [_row(DataEntryTypeEnum.planner_purchase_budget, {"amount_eur": 1000.0})]
    )
    with pytest.raises(HTTPException) as exc:
        await workflow._check_planner_purchase_exclusivity(
            1, DataEntryTypeEnum.planner_purchase_budget, {"amount_eur": 2000.0}
        )
    assert exc.value.detail == "PURCHASES_GLOBAL_BUDGET_EXISTS"


@pytest.mark.asyncio
async def test_update_excludes_edited_row_from_duplicate_scan():
    """Editing a row's own category (self) must not self-collide."""
    workflow = _workflow_with_rows(
        [
            _row(
                DataEntryTypeEnum.planner_purchase,
                {"purchase_category": "services", "amount_eur": 5.0},
                row_id=7,
            )
        ]
    )
    # Re-saving row 7 as 'services' is fine because it is excluded from the scan.
    await workflow._check_planner_purchase_exclusivity(
        1,
        DataEntryTypeEnum.planner_purchase,
        {"purchase_category": "services"},
        exclude_entry_id=7,
    )


def _dump(amount: float, currency: str | None) -> dict:
    payload = {"purchase_category": "services", "amount_eur": amount}
    if currency is not None:
        payload["currency"] = currency
    return {
        "data_entry_type_id": DataEntryTypeEnum.planner_purchase.value,
        "carbon_report_module_id": 1,
        **payload,
        "data": dict(payload),
    }


def _conversion_workflow() -> CarbonReportModuleWorkflow:
    return CarbonReportModuleWorkflow(
        MagicMock(get=AsyncMock(return_value=MagicMock()))
    )


@pytest.mark.asyncio
async def test_non_eur_amount_converted_and_currency_stripped():
    workflow = _conversion_workflow()
    patch(
        "app.workflows.carbon_report_module.resolve_factor_year",
        AsyncMock(return_value=2025),
    ).start()
    rates = MagicMock()
    rates.get_exchange_rate_to_eur.return_value = 0.94
    patch(
        "app.workflows.carbon_report_module.ExchangeRatesService",
        return_value=rates,
    ).start()
    out = await workflow._convert_planner_purchase_amount(
        MagicMock(carbon_report_id=3), _dump(1000.0, "chf")
    )
    assert out["amount_eur"] == pytest.approx(940.0)
    assert out["data"]["amount_eur"] == pytest.approx(940.0)
    assert "currency" not in out
    assert "currency" not in out["data"]
    rates.get_exchange_rate_to_eur.assert_called_once_with(2025, "chf")


@pytest.mark.asyncio
async def test_eur_amount_stored_verbatim_without_rate_lookup():
    workflow = _conversion_workflow()
    rates_cls = patch("app.workflows.carbon_report_module.ExchangeRatesService").start()
    for currency in ("eur", None):
        out = await workflow._convert_planner_purchase_amount(
            MagicMock(carbon_report_id=3), _dump(1000.0, currency)
        )
        assert out["amount_eur"] == 1000.0
        assert out["data"]["amount_eur"] == 1000.0
        assert "currency" not in out["data"]
    rates_cls.assert_not_called()


@pytest.mark.asyncio
async def test_unavailable_rate_rejected_as_422():
    workflow = _conversion_workflow()
    patch(
        "app.workflows.carbon_report_module.resolve_factor_year",
        AsyncMock(return_value=2030),
    ).start()
    rates = MagicMock()
    rates.get_exchange_rate_to_eur.side_effect = ValueError("no data")
    patch(
        "app.workflows.carbon_report_module.ExchangeRatesService",
        return_value=rates,
    ).start()
    with pytest.raises(HTTPException) as exc:
        await workflow._convert_planner_purchase_amount(
            MagicMock(carbon_report_id=3), _dump(1000.0, "chf")
        )
    assert exc.value.status_code == 422
    assert exc.value.detail == "PURCHASES_CURRENCY_RATE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_update_rejects_change_to_existing_category():
    """PATCHing a row's category to one another row already uses is rejected."""
    workflow = _workflow_with_rows(
        [
            _row(
                DataEntryTypeEnum.planner_purchase,
                {"purchase_category": "services", "amount_eur": 5.0},
                row_id=7,
            ),
            _row(
                DataEntryTypeEnum.planner_purchase,
                {"purchase_category": "vehicles", "amount_eur": 9.0},
                row_id=8,
            ),
        ]
    )
    with pytest.raises(HTTPException) as exc:
        await workflow._check_planner_purchase_exclusivity(
            1,
            DataEntryTypeEnum.planner_purchase,
            {"purchase_category": "services"},
            exclude_entry_id=8,
        )
    assert exc.value.detail == "DUPLICATE_PURCHASE_CATEGORY"
