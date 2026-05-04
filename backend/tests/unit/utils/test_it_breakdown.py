"""Unit tests for IT-focused emission breakdown."""

import pytest

from app.models.data_entry_emission import EmissionType
from app.models.module_type import ModuleTypeEnum
from app.utils.it_breakdown import (
    IT_CATEGORIES_ORDER,
    IT_CATEGORY_CLOUD_AI,
    IT_CATEGORY_EQUIPMENT,
    IT_CATEGORY_PURCHASES,
    IT_CATEGORY_RESEARCH,
    build_it_breakdown,
)


def _cat_by_key(categories: list[dict], key: str) -> dict:
    return next(c for c in categories if c["category_key"] == key)


class TestBuildItBreakdown:
    def test_basic_aggregation_from_all_sources(self):
        rows = [
            (
                ModuleTypeEnum.equipment_electric_consumption.value,
                EmissionType.equipment__it.value,
                5_000.0,
            ),
            (
                ModuleTypeEnum.purchase.value,
                EmissionType.purchases__it_equipment.value,
                3_000.0,
            ),
            (
                ModuleTypeEnum.external_cloud_and_ai.value,
                EmissionType.external__clouds__stockage.value,
                2_000.0,
            ),
        ]
        result = build_it_breakdown(rows, total_fte=10.0, total_emissions_kg=20_000.0)

        assert result["total_it_tonnes_co2eq"] == pytest.approx(10.0)
        assert result["total_it_per_fte"] == pytest.approx(1.0)
        assert result["percentage_of_total"] == pytest.approx(50.0)

        equip = _cat_by_key(result["categories"], IT_CATEGORY_EQUIPMENT)
        assert equip["tonnes_co2eq"] == pytest.approx(5.0)
        assert equip["percentage"] == pytest.approx(50.0)

        purch = _cat_by_key(result["categories"], IT_CATEGORY_PURCHASES)
        assert purch["tonnes_co2eq"] == pytest.approx(3.0)

        cloud = _cat_by_key(result["categories"], IT_CATEGORY_CLOUD_AI)
        assert cloud["tonnes_co2eq"] == pytest.approx(2.0)

    def test_empty_input_returns_zero_filled(self):
        result = build_it_breakdown([], total_fte=10.0, total_emissions_kg=100_000.0)

        assert result["total_it_tonnes_co2eq"] == 0.0
        assert result["total_it_per_fte"] == 0.0
        assert result["percentage_of_total"] == 0.0
        assert len(result["categories"]) == len(IT_CATEGORIES_ORDER)
        for cat in result["categories"]:
            assert cat["tonnes_co2eq"] == 0.0
            assert cat["percentage"] == 0.0

    def test_zero_fte_gives_zero_per_fte(self):
        rows = [
            (
                ModuleTypeEnum.equipment_electric_consumption.value,
                EmissionType.equipment__it.value,
                5_000.0,
            ),
        ]
        result = build_it_breakdown(rows, total_fte=0.0, total_emissions_kg=5_000.0)

        assert result["total_it_per_fte"] == 0.0
        assert result["total_it_tonnes_co2eq"] == pytest.approx(5.0)

    def test_zero_total_emissions_gives_zero_percentage(self):
        rows = [
            (
                ModuleTypeEnum.equipment_electric_consumption.value,
                EmissionType.equipment__it.value,
                5_000.0,
            ),
        ]
        result = build_it_breakdown(rows, total_emissions_kg=0.0)

        assert result["percentage_of_total"] == 0.0

    def test_non_it_rows_are_ignored(self):
        rows = [
            (
                ModuleTypeEnum.equipment_electric_consumption.value,
                EmissionType.equipment__scientific.value,
                10_000.0,
            ),
            (
                ModuleTypeEnum.equipment_electric_consumption.value,
                EmissionType.equipment__it.value,
                2_000.0,
            ),
            (
                ModuleTypeEnum.professional_travel.value,
                EmissionType.professional_travel__plane__eco.value,
                8_000.0,
            ),
        ]
        result = build_it_breakdown(rows, total_emissions_kg=20_000.0)

        assert result["total_it_tonnes_co2eq"] == pytest.approx(2.0)

    def test_scope_breakdown(self):
        rows = [
            (
                ModuleTypeEnum.equipment_electric_consumption.value,
                EmissionType.equipment__it.value,
                4_000.0,
            ),
            (
                ModuleTypeEnum.purchase.value,
                EmissionType.purchases__it_equipment.value,
                3_000.0,
            ),
            (
                ModuleTypeEnum.external_cloud_and_ai.value,
                EmissionType.external__clouds__calcul.value,
                1_000.0,
            ),
        ]
        result = build_it_breakdown(rows)

        assert result["scope_breakdown"]["scope_2"] == pytest.approx(4.0)
        assert result["scope_breakdown"]["scope_3"] == pytest.approx(4.0)

    def test_cloud_ai_detail_emissions(self):
        rows = [
            (
                ModuleTypeEnum.external_cloud_and_ai.value,
                EmissionType.external__clouds__stockage.value,
                1_000.0,
            ),
            (
                ModuleTypeEnum.external_cloud_and_ai.value,
                EmissionType.external__clouds__calcul.value,
                2_000.0,
            ),
            (
                ModuleTypeEnum.external_cloud_and_ai.value,
                EmissionType.external__ai__provider_openai.value,
                500.0,
            ),
            (
                ModuleTypeEnum.external_cloud_and_ai.value,
                EmissionType.external__ai__provider_anthropic.value,
                300.0,
            ),
        ]
        result = build_it_breakdown(rows)
        cloud = _cat_by_key(result["categories"], IT_CATEGORY_CLOUD_AI)

        emissions = {e["key"]: e["value"] for e in cloud["emissions"]}
        assert emissions["stockage"] == pytest.approx(1.0)
        assert emissions["calcul"] == pytest.approx(2.0)
        # AI providers grouped under "ai"
        assert emissions["ai"] == pytest.approx(0.8)

    def test_validation_all_validated(self):
        validated = {
            ModuleTypeEnum.equipment_electric_consumption.value,
            ModuleTypeEnum.purchase.value,
            ModuleTypeEnum.external_cloud_and_ai.value,
            ModuleTypeEnum.research_facilities.value,
        }
        result = build_it_breakdown(
            [],
            validated_module_type_ids=validated,
        )
        assert result["validated"] is True
        assert result["partially_validated"] is False
        assert len(result["validated_sources"]) == 4

    def test_validation_partial(self):
        validated = {ModuleTypeEnum.equipment_electric_consumption.value}
        result = build_it_breakdown(
            [],
            validated_module_type_ids=validated,
        )
        assert result["validated"] is False
        assert result["partially_validated"] is True
        assert result["validated_sources"] == [IT_CATEGORY_EQUIPMENT]

    def test_validation_none(self):
        result = build_it_breakdown([], validated_module_type_ids=set())
        assert result["validated"] is False
        assert result["partially_validated"] is False
        assert result["validated_sources"] == []

    def test_percentage_correctness(self):
        rows = [
            (
                ModuleTypeEnum.equipment_electric_consumption.value,
                EmissionType.equipment__it.value,
                3_000.0,
            ),
            (
                ModuleTypeEnum.purchase.value,
                EmissionType.purchases__it_equipment.value,
                7_000.0,
            ),
        ]
        result = build_it_breakdown(rows)

        equip = _cat_by_key(result["categories"], IT_CATEGORY_EQUIPMENT)
        purch = _cat_by_key(result["categories"], IT_CATEGORY_PURCHASES)
        assert equip["percentage"] == pytest.approx(30.0)
        assert purch["percentage"] == pytest.approx(70.0)

    def test_categories_order_is_deterministic(self):
        result = build_it_breakdown([])
        keys = [c["category_key"] for c in result["categories"]]
        assert keys == IT_CATEGORIES_ORDER

    def test_unknown_emission_type_id_ignored(self):
        rows = [
            (4, 999999, 5_000.0),
            (
                ModuleTypeEnum.equipment_electric_consumption.value,
                EmissionType.equipment__it.value,
                1_000.0,
            ),
        ]
        result = build_it_breakdown(rows)
        assert result["total_it_tonnes_co2eq"] == pytest.approx(1.0)

    def test_exclude_modules_drops_research_and_recomputes_percentage_denominator(self):
        rows = [
            (
                ModuleTypeEnum.equipment_electric_consumption.value,
                EmissionType.equipment__it.value,
                1_000.0,
            ),
            (
                ModuleTypeEnum.research_facilities.value,
                EmissionType.research_facilities.value,
                9_000.0,
            ),
        ]
        exclude = {ModuleTypeEnum.research_facilities.value}
        result = build_it_breakdown(
            rows,
            total_emissions_kg=10_000.0,
            exclude_module_type_ids=exclude,
        )
        assert result["total_it_tonnes_co2eq"] == pytest.approx(1.0)
        assert result["percentage_of_total"] == pytest.approx(100.0)
        research = _cat_by_key(result["categories"], IT_CATEGORY_RESEARCH)
        assert research["tonnes_co2eq"] == pytest.approx(0.0)

    def test_exclude_modules_omits_excluded_category_from_validation_requirement(self):
        validated = {
            ModuleTypeEnum.equipment_electric_consumption.value,
            ModuleTypeEnum.purchase.value,
            ModuleTypeEnum.external_cloud_and_ai.value,
        }
        exclude = {ModuleTypeEnum.research_facilities.value}
        result = build_it_breakdown(
            [],
            validated_module_type_ids=validated,
            exclude_module_type_ids=exclude,
        )
        assert result["validated"] is True
        assert IT_CATEGORY_RESEARCH not in result["validated_sources"]
