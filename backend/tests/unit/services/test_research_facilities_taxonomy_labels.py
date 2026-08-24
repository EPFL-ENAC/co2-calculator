"""#2007 — research facility options must read as acronyms, not unit codes.

`researchfacility_id` is an opaque unit code ("1902"); the acronym users know
the platform by ("SCITAS-GE") lives in `researchfacility_name`. The frontend
relabels select options from this taxonomy
(`ModuleForm.getFilteredOptions` → `taxoChildMap.get(opt.value).label`), so a
taxonomy that labels by id turns the whole facility dropdown into a list of
numbers — which is exactly what shipped before `kind_label_field` was set.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.schemas.data_entry import BaseModuleHandler
from app.services.module_handler_service import ModuleHandlerService

_COMMON_FACTORS = [
    SimpleNamespace(
        classification={
            "researchfacility_id": "1902",
            "researchfacility_name": "SCITAS-GE",
        },
        values={"use_unit": "CHF", "total_use": 2195625.795},
    ),
    SimpleNamespace(
        classification={
            "researchfacility_id": "0872",
            "researchfacility_name": "CAM-GE",
        },
        values={"use_unit": "%", "total_use": 100},
    ),
]

_ANIMAL_FACTORS = [
    SimpleNamespace(
        classification={
            "researchfacility_id": "1321",
            "researchfacility_name": "CPG",
            "researchfacility_type": "rodent",
        },
        values={"use_unit": "housings", "total_use": 3917},
    ),
    SimpleNamespace(
        classification={
            "researchfacility_id": "1321",
            "researchfacility_name": "CPG",
            "researchfacility_type": "fish",
        },
        values={"use_unit": "housings", "total_use": 602},
    ),
]


def _service(factors: list) -> ModuleHandlerService:
    service = ModuleHandlerService(MagicMock())
    service.factor_service = MagicMock()
    service.factor_service.list_by_data_entry_type = AsyncMock(return_value=factors)
    return service


@pytest.mark.asyncio
async def test_common_facilities_are_labelled_by_acronym():
    det = DataEntryTypeEnum.research_facilities
    handler = BaseModuleHandler.get_by_type(det)

    taxonomy = await _service(_COMMON_FACTORS).get_taxonomy(handler, det, 2025)

    # name stays the id (it is the stored value the select submits), label is
    # what the user reads.
    assert {(c.name, c.label) for c in taxonomy.children} == {
        ("1902", "SCITAS-GE"),
        ("0872", "CAM-GE"),
    }


@pytest.mark.asyncio
async def test_animal_facilities_are_labelled_by_acronym():
    det = DataEntryTypeEnum.animal_facilities
    handler = BaseModuleHandler.get_by_type(det)

    taxonomy = await _service(_ANIMAL_FACTORS).get_taxonomy(handler, det, 2025)

    # One facility, two housing types beneath it.
    assert [(c.name, c.label) for c in taxonomy.children] == [("1321", "CPG")]
    assert {c.name for c in taxonomy.children[0].children} == {"rodent", "fish"}


@pytest.mark.asyncio
async def test_no_facility_is_labelled_with_its_unit_code():
    """The regression itself: a label equal to the id means the dropdown shows
    numbers.
    """
    for det, factors in (
        (DataEntryTypeEnum.research_facilities, _COMMON_FACTORS),
        (DataEntryTypeEnum.animal_facilities, _ANIMAL_FACTORS),
    ):
        handler = BaseModuleHandler.get_by_type(det)
        taxonomy = await _service(factors).get_taxonomy(handler, det, 2025)
        assert all(c.label != c.name for c in taxonomy.children)
