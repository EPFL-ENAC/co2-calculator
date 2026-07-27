"""Deriving the planner purchase factors from the Calculator's."""

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions import EmissionType
from app.modules_planner.purchase.derived_factors import (
    PLANNER_EF_KEY,
    SOURCE_TYPE_BY_CATEGORY,
    build_factors,
    category_means,
    global_mean,
)


def test_a_category_factor_is_the_mean_of_its_codes():
    means = category_means({"services": [0.2, 0.4, 0.9]})
    assert means["services"] == pytest.approx(0.5)


def test_a_category_without_source_factors_is_left_unpriced():
    means = category_means({"services": [0.3], "vehicles": []})
    assert set(means) == {"services"}


def test_every_planner_category_maps_to_a_calculator_type():
    assert SOURCE_TYPE_BY_CATEGORY["it_equipment"] is DataEntryTypeEnum.it_equipment
    assert len(SOURCE_TYPE_BY_CATEGORY) == 7


def test_global_budget_weights_categories_not_codes():
    # 'services' has one code and 'vehicles' three; both still count once.
    means = category_means({"services": [0.2], "vehicles": [0.3, 0.4, 0.5]})
    assert global_mean(means) == pytest.approx(0.3)


def test_build_factors_emits_one_row_per_category_plus_the_budget():
    factors = build_factors({"services": 0.2, "vehicles": 0.4}, year=2025)

    per_category = [
        f
        for f in factors
        if f.data_entry_type_id == DataEntryTypeEnum.planner_purchase.value
    ]
    assert {f.classification["purchase_category"] for f in per_category} == {
        "services",
        "vehicles",
    }
    assert {f.emission_type_id for f in per_category} == {
        EmissionType.purchases__services.value,
        EmissionType.purchases__vehicles.value,
    }
    assert all(f.year == 2025 for f in factors)

    budget = next(
        f
        for f in factors
        if f.data_entry_type_id == DataEntryTypeEnum.planner_purchase_budget.value
    )
    # The global budget resolves with no classification (kind is None).
    assert budget.classification == {}
    assert budget.emission_type_id == EmissionType.purchases__goods_and_services.value
    assert budget.values[PLANNER_EF_KEY] == pytest.approx(0.3)
