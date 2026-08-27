from pydantic import field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions import EmissionType
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)

## PURCHASE FACTOR HANDLERS

# --- Centralized Purchases ---

purchase_additional_classification_fields: list[str] = ["name"]
purchase_additional_value_fields: list[str] = ["ef_kg_co2eq_per_kg"]


class PurchaseCentralizedFactorCreate(FactorCreate):
    name: str
    ef_kg_co2eq_per_kg: float

    @field_validator("ef_kg_co2eq_per_kg", mode="after")
    @classmethod
    def validate_ef(cls, v: float) -> float:
        if v < 0:
            raise ValueError("ef_kg_co2eq_per_kg must be non-negative")
        return v


class PurchaseCentralizedFactorUpdate(FactorUpdate):
    name: str | None = None
    ef_kg_co2eq_per_kg: float | None = None

    @field_validator("ef_kg_co2eq_per_kg", mode="after")
    @classmethod
    def validate_ef(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < 0:
            raise ValueError("ef_kg_co2eq_per_kg must be non-negative")
        return v


class PurchaseCentralizedFactorResponse(FactorResponseGen):
    name: str
    ef_kg_co2eq_per_kg: float


class PurchaseCentralizedFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.purchases_centralized]
    emission_type = EmissionType.purchases__centralized

    create_dto = PurchaseCentralizedFactorCreate
    update_dto = PurchaseCentralizedFactorUpdate
    response_dto = PurchaseCentralizedFactorResponse

    classification_fields: list[str] = purchase_additional_classification_fields
    value_fields: list[str] = purchase_additional_value_fields


# --- Common Purchases (7 types, same CSV format) ---

purchase_common_classification_fields: list[str] = [
    "purchase_institutional_code",
    "purchase_additional_code",
    "currency",
]
purchase_common_value_fields: list[str] = [
    "ef_kg_co2eq_per_currency",
    "translation_key",
]


class PurchaseCommonFactorCreate(FactorCreate):
    currency: str
    purchase_institutional_code: str
    translation_key: str | None = None
    purchase_additional_code: str | None = None
    ef_kg_co2eq_per_currency: float
    # purchase_category: str  # only for upload Mandatory (checked in csv upload)
    # purchase_category is the routing column (picks the correct data_entry_type).
    # It is consumed in the factor CSV provider, not carried on this DTO —
    # its presence + case-sensitive enum is enforced
    # there (see base_factor_csv_provider._resolve_data_entry_type).

    @field_validator("ef_kg_co2eq_per_currency", mode="after")
    @classmethod
    def validate_ef(cls, v: float) -> float:
        if v < 0:
            raise ValueError("ef_kg_co2eq_per_currency must be non-negative")
        return v

    @field_validator("purchase_institutional_code", mode="after")
    @classmethod
    def validate_institutional_code(cls, v: str) -> str:
        # Always present on factors: the additional-code-less rows are the
        # per-institutional-code averages, so a factor without an
        # institutional code could never be matched.
        if not v.strip():
            raise ValueError("purchase_institutional_code must not be empty")
        return v


class PurchaseCommonFactorUpdate(FactorUpdate):
    purchase_institutional_code: str | None = None
    purchase_additional_code: str | None = None
    currency: str | None = None
    ef_kg_co2eq_per_currency: float | None = None
    translation_key: str | None = None


class PurchaseCommonFactorResponse(FactorResponseGen):
    purchase_institutional_code: str
    purchase_additional_code: str | None = None
    currency: str
    ef_kg_co2eq_per_currency: float | None = None
    translation_key: str | None = None


class PurchaseCommonFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [
        DataEntryTypeEnum.scientific_equipment,
        DataEntryTypeEnum.it_equipment,
        DataEntryTypeEnum.consumable_accessories,
        DataEntryTypeEnum.biological_chemical_gaseous_product,
        DataEntryTypeEnum.services,
        DataEntryTypeEnum.vehicles,
        DataEntryTypeEnum.other_purchases,
    ]
    category_field: str = "purchase_category"
    emission_type = None  # resolved per type via DATA_ENTRY_TO_EMISSION_TYPES

    create_dto = PurchaseCommonFactorCreate
    update_dto = PurchaseCommonFactorUpdate
    response_dto = PurchaseCommonFactorResponse

    classification_fields: list[str] = purchase_common_classification_fields
    value_fields: list[str] = purchase_common_value_fields
