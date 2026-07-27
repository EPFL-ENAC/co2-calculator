"""Unit tests for IT categorisation over flat by_emission_type maps."""

from app.modules.emissions.taxonomy import EmissionType
from app.utils.it_breakdown import (
    IT_CATEGORY_CLOUD_AI,
    IT_CATEGORY_EQUIPMENT,
    IT_CATEGORY_RESEARCH,
    build_cloud_ai_detail,
    build_it_category_totals,
)


def test_category_totals_count_leaves_only():
    by_et = {
        str(EmissionType.equipment__it.value): 100.0,
        # rollup entries must be ignored (their value duplicates the leaves)
        str(EmissionType.equipment.value): 100.0,
        str(EmissionType.external__clouds__calcul.value): 10.0,
        str(EmissionType.external__clouds.value): 10.0,
        str(EmissionType.external.value): 10.0,
        # non-IT leaf
        str(EmissionType.food__vegetarian.value): 5.0,
    }
    totals = build_it_category_totals(by_et)
    assert totals[IT_CATEGORY_EQUIPMENT] == 100.0
    assert totals[IT_CATEGORY_CLOUD_AI] == 10.0
    assert sum(totals.values()) == 110.0


def test_animal_facilities_are_not_it():
    by_et = {
        str(EmissionType.research_facilities__facilities.value): 40.0,
        str(EmissionType.research_facilities__it_facilities.value): 60.0,
        str(EmissionType.research_facilities__animal__rodent.value): 30.0,
        str(EmissionType.research_facilities__animal__fish.value): 20.0,
        str(EmissionType.research_facilities__animal.value): 50.0,
        str(EmissionType.research_facilities.value): 150.0,
    }
    totals = build_it_category_totals(by_et)
    assert totals[IT_CATEGORY_RESEARCH] == 100.0


def test_cloud_ai_detail_groups_ai_providers():
    by_et = {
        str(EmissionType.external__clouds__calcul.value): 10.0,
        str(EmissionType.external__clouds__stockage.value): 20.0,
        str(EmissionType.external__ai__provider_openai.value): 1.0,
        str(EmissionType.external__ai__provider_anthropic.value): 2.0,
    }
    detail = build_cloud_ai_detail(by_et)
    assert detail == {"calcul": 10.0, "stockage": 20.0, "ai": 3.0}
