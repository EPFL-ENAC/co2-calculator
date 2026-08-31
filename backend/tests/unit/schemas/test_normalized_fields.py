"""Regression tests for the shared normalized join-key types (#1489).

Factor resolution compares ``factor.classification[k]`` to ``entry.data[k]``
by exact string equality, so both DTO families must produce the same
canonical form, the persisted ``data`` payload must carry the normalized
value (not the raw one), and the data migration must rewrite existing factor
rows to the very same form. Each of those three legs gets pinned here.
"""

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.modules.professional_travel.data_entries import (
    ProfessionalTravelTrainHandlerCreate,
)
from app.modules.purchase.data_entries import PurchaseHandlerCreate
from app.schemas.data_entry import BaseModuleHandler
from app.schemas.fields import (
    ROW_COUNTRY_CODE,
    ClassificationKey,
    CountryCode,
    CurrencyCode,
    IdentifierKey,
    OptionalClassificationKey,
)
from app.services.factor_resolver import FactorResolver


class _Aliases(BaseModel):
    currency: CurrencyCode = "chf"
    country: CountryCode = "CH"
    key: ClassificationKey = "x"
    optional_key: OptionalClassificationKey = None
    identifier: IdentifierKey = "1"


# ===================== alias canonical forms =====================


@pytest.mark.parametrize("raw", ["CHF", " chf ", "Chf"])
def test_currency_lowercased_and_stripped(raw):
    assert _Aliases(currency=raw).currency == "chf"


@pytest.mark.parametrize("raw", [" fr ", "fr", "FR"])
def test_country_code_uppercased_and_stripped(raw):
    assert _Aliases(country=raw).country == "FR"


@pytest.mark.parametrize("raw", ["RoW", "row", "ROW", " Row "])
def test_row_sentinel_keeps_its_mixed_case(raw):
    # "RoW" is the rest-of-world fallback literal factor CSVs ship; uppering
    # it would orphan every factor row keyed on the sentinel.
    assert _Aliases(country=raw).country == ROW_COUNTRY_CODE


def test_classification_key_strips_but_keeps_case():
    assert _Aliases(key=" Ultra Centrifuges ").key == "Ultra Centrifuges"


@pytest.mark.parametrize("raw", ["", "   "])
def test_optional_key_blank_becomes_none(raw):
    # Matches the CSV provider convention: an absent optional key is stored
    # as None in classification, never as "".
    assert _Aliases(optional_key=raw).optional_key is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1, "1"),
        (1.0, "1"),
        ("1.0", "1"),
        (" 1.0 ", "1"),
        ("007", "007"),
        ("AB-1.0", "AB-1.0"),
    ],
)
def test_identifier_spreadsheet_numeric_forms_collapse(raw, expected):
    assert _Aliases(identifier=raw).identifier == expected


@pytest.mark.parametrize("field", ["currency", "country", "key", "identifier"])
def test_required_aliases_reject_whitespace_only(field):
    with pytest.raises(ValidationError):
        _Aliases(**{field: "   "})


@pytest.mark.parametrize(
    ("field", "value"),
    [("country", 42), ("identifier", True), ("optional_key", 42)],
)
def test_non_string_inputs_pass_through_and_fail_type_check(field, value):
    # The before-validators leave non-strings untouched so pydantic's own
    # str type error surfaces instead of a confusing normalization error.
    with pytest.raises(ValidationError, match="valid string"):
        _Aliases(**{field: value})


# ===================== normalized value reaches ``data`` =====================


def _purchase_payload(**overrides):
    payload = {
        "data_entry_type_id": DataEntryTypeEnum.consumable_accessories.value,
        "carbon_report_module_id": 1,
        "name": "Pipette tips",
        "total_spent_amount": 100.0,
        "currency": "CHF",
        "purchase_institutional_code": " 51100000 ",
    }
    payload.update(overrides)
    return payload


def test_normalized_values_are_synced_into_data():
    """The persisted payload is ``dto.data``, not the typed fields.

    ``unflatten_payload`` copies the RAW payload into ``data`` before field
    validators run, so without the after-validator sync the entry would
    persist "CHF" while the factor identity says "chf" and resolution would
    silently miss (#1489).
    """
    dto = PurchaseHandlerCreate.model_validate(_purchase_payload())
    assert dto.currency == "chf"
    assert dto.data["currency"] == "chf"
    assert dto.data["purchase_institutional_code"] == "51100000"


def test_country_codes_synced_into_data():
    dto = ProfessionalTravelTrainHandlerCreate.model_validate(
        {
            "data_entry_type_id": DataEntryTypeEnum.train.value,
            "carbon_report_module_id": 1,
            "origin_name": "Lausanne",
            "destination_name": "Lyon",
            "origin_country_code": " ch ",
            "destination_country_code": "fr",
            "cabin_class": "second",
            "user_institutional_id": "123456",
        }
    )
    assert dto.data["origin_country_code"] == "CH"
    assert dto.data["destination_country_code"] == "FR"


# ===================== normalized entry resolves the factor ==================


PURCHASE_DET = DataEntryTypeEnum.consumable_accessories
PURCHASE_HANDLER = BaseModuleHandler.get_by_type(PURCHASE_DET)


@pytest.mark.asyncio
async def test_normalized_entry_data_resolves_canonical_factor():
    """Entry typed with whitespace/casing noise still finds its factor."""
    factor = Factor(
        id=1,
        data_entry_type_id=PURCHASE_DET.value,
        emission_type_id=1,
        classification={
            "purchase_institutional_code": "51100000",
            "purchase_additional_code": None,
            "currency": "chf",
        },
        values={"ef_kg_co2eq_per_currency": 0.41},
        year=2025,
    )
    dto = PurchaseHandlerCreate.model_validate(_purchase_payload())
    with patch(
        "app.services.factor_resolver.FactorRepository.list_by_data_entry_type",
        new=AsyncMock(return_value=[factor]),
    ):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(PURCHASE_HANDLER, dto.data, PURCHASE_DET, 2025)
    assert got is not None and got.id == 1


# ===================== migration mirrors the DTO forms =======================


def _load_migration() -> ModuleType:
    path = (
        Path(__file__).parents[3]
        / "alembic"
        / "versions"
        / "2026_08_31_1935-09fe9e551783_normalize_factor_classification_join_.py"
    )
    spec = importlib.util.spec_from_file_location("migration_09fe9e551783", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration module at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_normalization_matches_dto_normalization():
    """The migration must land existing rows on the exact DTO canonical form.

    Any divergence recreates the bug the migration fixes: a factor identity
    the normalized DTOs can never produce again.
    """
    migration = _load_migration()
    got = migration.normalize_classification(
        {
            "currency": " CHF ",
            "cabin_class": "Economy",
            "energy_type": "Thermal",
            "country_code": "fr",
            "researchfacility_id": "12.0",
            "name": " Ultra Centrifuges ",
            "purchase_additional_code": "  ",
        }
    )
    assert got == {
        "currency": "chf",
        "cabin_class": "economy",
        "energy_type": "thermal",
        "country_code": "FR",
        "researchfacility_id": "12",
        "name": "Ultra Centrifuges",
        "purchase_additional_code": None,
    }


def test_migration_keeps_row_sentinel_and_non_strings():
    migration = _load_migration()
    got = migration.normalize_classification(
        {"country_code": "row", "year_like": 3, "absent": None}
    )
    assert got == {
        "country_code": ROW_COUNTRY_CODE,
        "year_like": 3,
        "absent": None,
    }
