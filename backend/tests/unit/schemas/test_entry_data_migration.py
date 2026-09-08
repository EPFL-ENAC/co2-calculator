"""Migration cf237968fba7 (#2592) mirrors the entry DTO normalization.

The migration carries its own copies of the key map and the value rules
(a migration must not import app code that can change under it). These
tests pin both copies to the live ``*HandlerCreate`` DTOs and the shared
field types so the two sides cannot drift: a new normalized key on a DTO
without a matching migration entry fails here.
"""

import importlib.util
from pathlib import Path
from types import ModuleType
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

_MIGRATION_FILE = "2026_09_08_1029-cf237968fba7_normalize_entry_data_join_keys.py"


def _load_migration() -> ModuleType:
    path = Path(__file__).parents[3] / "alembic" / "versions" / _MIGRATION_FILE
    spec = importlib.util.spec_from_file_location("migration_cf237968fba7", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration module at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = _load_migration()

_RULE_BY_VALIDATOR = {
    "_normalize_country_code": migration.COUNTRY,
    "_coerce_numeric_identifier": migration.IDENTIFIER,
    "_blank_to_none": migration.BLANK_TO_NONE,
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
            return migration.LOWER
        if isinstance(item, StringConstraints) and item.strip_whitespace:
            return migration.STRIP
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
            rules["cabin_class"] = migration.LOWER
        if rules:
            rules_by_det[det.value] = rules
    return rules_by_det


def test_migration_key_map_matches_entry_dtos() -> None:
    expected = _rules_from_dtos()
    assert migration.RULES_BY_DATA_ENTRY_TYPE == expected, (
        "add the new normalized key to RULES_BY_DATA_ENTRY_TYPE in the migration"
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
def test_migration_value_rules_match_shared_types(rule: str, raw: object) -> None:
    via_dto = getattr(_Aliases.model_validate({rule: raw}), rule)
    assert migration.normalize_value(rule, raw) == via_dto


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
    normalized = migration.normalize_entry_data(det, data)
    assert normalized == {
        "name": "Pipette",
        "currency": "chf",
        "purchase_additional_code": None,
        "total_spent_amount": 12.5,
        "note": "  keep me  ",
        "supplier": " ACME ",
    }
    assert migration.normalize_entry_data(det, normalized) == normalized
    assert set(normalized) == set(data), "keys are never added or dropped"


def test_normalize_entry_data_leaves_unmapped_types_alone() -> None:
    data = {"name": " X ", "sius_code": " 51 "}
    assert migration.normalize_entry_data(DataEntryTypeEnum.member.value, data) == data
