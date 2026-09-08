"""``scripts/normalize_join_keys.py`` mirrors the entry DTO normalization.

The script carries its own copies of the key map and the value rules. These
tests pin both to the live ``*HandlerCreate`` DTOs and the shared field types
so the two sides cannot drift: a new normalized key on a DTO without a
matching script entry fails here.
"""

from typing import Annotated, get_args, get_origin

import pytest
from pydantic import BaseModel, BeforeValidator, StringConstraints
from pydantic.fields import FieldInfo

from app.models.data_entry import DataEntryTypeEnum
from app.schemas.data_entry import BaseModuleHandler
from app.schemas.fields import (
    ClassificationKey,
    CountryCode,
    CurrencyCode,
    IdentifierKey,
    OptionalClassificationKey,
)
from scripts import normalize_join_keys as script

_RULE_BY_VALIDATOR = {
    "_normalize_country_code": script.COUNTRY,
    "_coerce_numeric_identifier": script.IDENTIFIER,
    "_blank_to_none": script.BLANK_TO_NONE,
}


def _annotated_metadata(field: FieldInfo) -> list:
    metadata = list(field.metadata)
    # ``Alias | None`` keeps the Annotated inside the union, not on the field.
    for arg in get_args(field.annotation) or (field.annotation,):
        if get_origin(arg) is Annotated:
            metadata.extend(arg.__metadata__)
    return metadata


def _rule_for(field: FieldInfo) -> str | None:
    metadata = _annotated_metadata(field)
    for item in metadata:
        if isinstance(item, BeforeValidator):
            return _RULE_BY_VALIDATOR[item.func.__name__]
    for item in metadata:
        if isinstance(item, StringConstraints) and item.to_lower:
            return script.LOWER
        if isinstance(item, StringConstraints) and item.strip_whitespace:
            return script.STRIP
    return None


def _rules_from_dtos() -> dict[int, dict[str, str]]:
    rules_by_det: dict[int, dict[str, str]] = {}
    for det in DataEntryTypeEnum:
        try:
            handler = BaseModuleHandler.get_by_type(det)
        except ValueError:
            continue
        dto = handler.create_dto
        rules = {
            name: rule
            for name, field in dto.model_fields.items()
            if (rule := _rule_for(field)) is not None
        }
        # cabin_class is normalized by the travel mixins, not a shared alias
        if "cabin_class" in dto.model_fields:
            rules["cabin_class"] = script.LOWER
        if rules:
            rules_by_det[det.value] = rules
    return rules_by_det


def test_script_key_map_matches_entry_dtos() -> None:
    assert script.RULES_BY_DATA_ENTRY_TYPE == _rules_from_dtos(), (
        "add the new normalized key to RULES_BY_DATA_ENTRY_TYPE in the script"
    )


class _Aliases(BaseModel):
    strip: ClassificationKey = "x"
    lower: CurrencyCode = "x"
    country: CountryCode = "x"
    identifier: IdentifierKey = "x"
    blank_to_none: OptionalClassificationKey = None


@pytest.mark.parametrize(
    ("rule", "raw"),
    [
        ("strip", " Freezer "),
        ("strip", "Ultra centrifuges"),
        ("lower", " CHF "),
        ("lower", "eur"),
        ("country", " fr "),
        ("country", "row"),
        ("country", "RoW"),
        ("country", "CH"),
        ("identifier", " 1.0 "),
        ("identifier", "1"),
        ("identifier", 1),
        ("identifier", 1.0),
        ("identifier", "007"),
        ("identifier", "1.50"),
        ("blank_to_none", "   "),
        ("blank_to_none", ""),
        ("blank_to_none", " LA05 "),
        ("blank_to_none", None),
    ],
)
def test_script_value_rules_match_shared_types(rule: str, raw: object) -> None:
    via_dto = getattr(_Aliases.model_validate({rule: raw}), rule)
    assert script.normalize_value(rule, raw) == via_dto


def test_normalize_entry_data_touches_only_mapped_string_keys() -> None:
    det = DataEntryTypeEnum.consumable_accessories.value
    data = {
        "name": " Pipette ",
        "currency": "CHF",
        "purchase_additional_code": "  ",
        "total_spent_amount": 12.5,
        "note": "  keep me  ",
        "supplier": " ACME ",
    }
    normalized = script.normalize_entry_data(det, data)
    assert normalized == {
        "name": "Pipette",
        "currency": "chf",
        "purchase_additional_code": None,
        "total_spent_amount": 12.5,
        "note": "  keep me  ",
        "supplier": " ACME ",
    }
    assert script.normalize_entry_data(det, normalized) == normalized
    assert set(normalized) == set(data), "keys are never added or dropped"


def test_normalize_entry_data_leaves_unmapped_types_alone() -> None:
    data = {"name": " X ", "sius_code": " 51 "}
    assert script.normalize_entry_data(DataEntryTypeEnum.member.value, data) == data
