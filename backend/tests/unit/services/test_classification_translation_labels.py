"""#2401 — classification labels localize via the translation table.

Covers both handler shapes the taxonomy builder supports:
- equipment (self-labeling field): the classification value itself is the
  English label, e.g. `equipment_class="Engine"`, translated by a row keyed
  on `("equipment_class", "Engine", "fr")`.
- research_facilities (code + separate label field): `kind_label_field`
  points at a different classification field holding the English text,
  translated by a row keyed on that label field instead.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.factor_taxonomy_cache import taxonomy_cache
from app.models.data_entry import DataEntryTypeEnum
from app.schemas.data_entry import BaseModuleHandler
from app.services.module_handler_service import ModuleHandlerService


@pytest.fixture(autouse=True)
def _clear_taxonomy_cache():
    # The module-level tree cache is keyed on (det, year, lang); several
    # tests below reuse the same det+year with different lang/translation
    # setups, which would otherwise collide with a real HTTP request's
    # cache (see module_handler_service.get_taxonomy_with_etag).
    taxonomy_cache.clear()
    yield
    taxonomy_cache.clear()


_EQUIPMENT_FACTORS = [
    SimpleNamespace(
        classification={"equipment_class": "Engine", "sub_class": None},
        values={},
    ),
    SimpleNamespace(
        classification={
            "equipment_class": "Engine",
            "sub_class": "Large Motor/Generator",
        },
        values={},
    ),
]

_RESEARCH_FACILITY_FACTORS = [
    SimpleNamespace(
        classification={
            "researchfacility_id": "1902",
            "researchfacility_name": "SCITAS-GE",
        },
        values={"use_unit": "CHF", "total_use": 1},
    ),
]


def _service(factors: list, translations: dict) -> ModuleHandlerService:
    service = ModuleHandlerService(MagicMock())
    service.factor_service = MagicMock()
    service.factor_service.list_by_data_entry_type = AsyncMock(return_value=factors)
    service.translation_repo = MagicMock()
    service.translation_repo.get_labels = AsyncMock(return_value=translations)
    return service


@pytest.mark.asyncio
async def test_english_never_queries_translations():
    det = DataEntryTypeEnum.scientific
    handler = BaseModuleHandler.get_by_type(det)
    service = _service(_EQUIPMENT_FACTORS, translations={})

    taxonomy = await service.get_taxonomy(handler, det, 2025, lang="en")

    service.translation_repo.get_labels.assert_not_called()
    assert taxonomy.children[0].label == "Engine"
    assert taxonomy.children[0].children[0].label == "Large Motor/Generator"


@pytest.mark.asyncio
async def test_self_labeling_field_translates_when_present():
    det = DataEntryTypeEnum.scientific
    handler = BaseModuleHandler.get_by_type(det)
    translations = {
        ("equipment_class", "Engine"): "Moteurs",
        ("sub_class", "Large Motor/Generator"): "Gros moteur/Générateur",
    }
    service = _service(_EQUIPMENT_FACTORS, translations)

    taxonomy = await service.get_taxonomy(handler, det, 2025, lang="fr")

    kind = taxonomy.children[0]
    assert kind.name == "Engine"  # `name` stays the raw value — factor
    # resolution keys on it (classification->>'equipment_class').
    assert kind.label == "Moteurs"
    assert kind.children[0].label == "Gros moteur/Générateur"


@pytest.mark.asyncio
async def test_self_labeling_field_falls_back_to_english_when_untranslated():
    """Empty `_fr` cell at ingestion = no row here = English label shown."""
    det = DataEntryTypeEnum.scientific
    handler = BaseModuleHandler.get_by_type(det)
    service = _service(_EQUIPMENT_FACTORS, translations={})

    taxonomy = await service.get_taxonomy(handler, det, 2025, lang="fr")

    assert taxonomy.children[0].label == "Engine"


@pytest.mark.asyncio
async def test_locale_with_region_normalizes_to_short_code():
    det = DataEntryTypeEnum.scientific
    handler = BaseModuleHandler.get_by_type(det)
    service = _service(
        _EQUIPMENT_FACTORS, translations={("equipment_class", "Engine"): "Moteurs"}
    )

    taxonomy = await service.get_taxonomy(handler, det, 2025, lang="fr-CH")

    service.translation_repo.get_labels.assert_awaited_once()
    assert service.translation_repo.get_labels.await_args.args[1] == "fr"
    assert taxonomy.children[0].label == "Moteurs"


@pytest.mark.asyncio
async def test_kind_label_field_shape_translates_by_label_field_not_code():
    """Purchase's shape (#2391 decision 4): the grouping value is an opaque
    code, so the translation is keyed on `kind_label_field`'s English text,
    not on the code itself.
    """
    det = DataEntryTypeEnum.research_facilities
    handler = BaseModuleHandler.get_by_type(det)
    translations = {("researchfacility_name", "SCITAS-GE"): "SCITAS-GE (FR)"}
    service = _service(_RESEARCH_FACILITY_FACTORS, translations)

    taxonomy = await service.get_taxonomy(handler, det, 2025, lang="fr")

    node = taxonomy.children[0]
    assert node.name == "1902"  # identity stays the code
    assert node.label == "SCITAS-GE (FR)"
