"""Planner purchase kinds: validation and emission resolution."""

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions import EmissionType
from app.modules.emissions.registry import resolve_emission_types
from app.modules_planner.purchase import (
    PlannerPurchaseBudgetCreate,
    PlannerPurchaseCreate,
)


def test_planner_purchase_create_validates_category():
    dto = PlannerPurchaseCreate(
        data_entry_type_id=DataEntryTypeEnum.planner_purchase.value,
        carbon_report_module_id=1,
        purchase_category="services",
        amount_eur=1500.0,
    )
    assert dto.data["purchase_category"] == "services"

    with pytest.raises(ValueError):
        PlannerPurchaseCreate(
            data_entry_type_id=DataEntryTypeEnum.planner_purchase.value,
            carbon_report_module_id=1,
            purchase_category="not-a-category",
            amount_eur=1500.0,
        )


def test_planner_purchase_rejects_negative_amount():
    with pytest.raises(ValueError):
        PlannerPurchaseBudgetCreate(
            data_entry_type_id=DataEntryTypeEnum.planner_purchase_budget.value,
            carbon_report_module_id=1,
            amount_eur=-1.0,
        )


def test_planner_purchase_currency_normalizes_and_defaults():
    dto = PlannerPurchaseCreate(
        data_entry_type_id=DataEntryTypeEnum.planner_purchase.value,
        carbon_report_module_id=1,
        purchase_category="services",
        amount_eur=1500.0,
        currency=" CHF ",
    )
    assert dto.currency == "chf"

    dto = PlannerPurchaseBudgetCreate(
        data_entry_type_id=DataEntryTypeEnum.planner_purchase_budget.value,
        carbon_report_module_id=1,
        amount_eur=1500.0,
        currency="",
    )
    assert dto.currency is None

    dto = PlannerPurchaseBudgetCreate(
        data_entry_type_id=DataEntryTypeEnum.planner_purchase_budget.value,
        carbon_report_module_id=1,
        amount_eur=1500.0,
    )
    assert dto.currency is None


def test_planner_purchase_rejects_unknown_currency():
    with pytest.raises(ValueError):
        PlannerPurchaseCreate(
            data_entry_type_id=DataEntryTypeEnum.planner_purchase.value,
            carbon_report_module_id=1,
            purchase_category="services",
            amount_eur=1500.0,
            currency="btc",
        )


def test_submodule_total_resolves_matching_purchases_emission():
    resolved = resolve_emission_types(
        DataEntryTypeEnum.planner_purchase, {"purchase_category": "vehicles"}
    )
    assert resolved == [EmissionType.purchases__vehicles]
    assert (
        resolve_emission_types(
            DataEntryTypeEnum.planner_purchase, {"purchase_category": "bogus"}
        )
        is None
    )


def test_global_budget_resolves_generic_purchases_node():
    resolved = resolve_emission_types(
        DataEntryTypeEnum.planner_purchase_budget, {"amount_eur": 1000.0}
    )
    assert resolved == [EmissionType.purchases__goods_and_services]
