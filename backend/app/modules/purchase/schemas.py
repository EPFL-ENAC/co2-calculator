from typing import Optional

from pydantic import field_validator

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    EmissionType,
)
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)

logger = get_logger(__name__)


class PurchaseHandlerResponse(DataEntryResponseGen):
    name: str
    supplier: Optional[str] = None
    quantity: Optional[float] = None
    total_spent_amount: float
    purchase_institutional_code: Optional[str] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class PurchaseAdditionalHandlerResponse(DataEntryResponseGen):
    name: str
    unit: Optional[str] = None
    annual_consumption: float
    coef_to_kg: float
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class PurchaseHandlerCreate(DataEntryCreate):
    name: str
    supplier: Optional[str] = None
    quantity: Optional[float] = None
    total_spent_amount: float
    currency: Optional[str] = None
    purchase_institutional_code: Optional[str] = None
    purchase_institutional_description: Optional[str] = None
    purchase_additional_code: Optional[str] = None
    note: Optional[str] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Quantity must be non-negative")
        return v

    @field_validator("total_spent_amount", mode="after")
    @classmethod
    def validate_total_spent_amount(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Total spend amount must be non-negative")
        return v

    @field_validator("purchase_institutional_code", mode="after")
    @classmethod
    def validate_purchase_institutional_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 1:
            raise ValueError(
                "Purchase institutional code must be at least 1 character long"
            )
        return v


class PurchaseAdditionalHandlerCreate(DataEntryCreate):
    name: str
    unit: str
    annual_consumption: Optional[float] = 0
    coef_to_kg: float
    note: Optional[str] = None

    @field_validator("annual_consumption", "coef_to_kg", mode="after")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


class PurchaseHandlerUpdate(DataEntryUpdate):
    name: Optional[str] = None
    supplier: Optional[str] = None
    quantity: Optional[float] = None
    total_spent_amount: Optional[float] = None
    currency: Optional[str] = None
    purchase_institutional_code: Optional[str] = None
    purchase_institutional_description: Optional[str] = None
    purchase_additional_code: Optional[str] = None
    note: Optional[str] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Quantity must be non-negative")
        return v

    @field_validator("total_spent_amount", mode="after")
    @classmethod
    def validate_total_spent_amount(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Total spend amount must be non-negative")
        return v


class PurchaseAdditionalHandlerUpdate(DataEntryUpdate):
    name: Optional[str] = None
    unit: Optional[str] = None
    annual_consumption: Optional[float] = None
    coef_to_kg: Optional[float] = None
    note: Optional[str] = None

    @field_validator("annual_consumption", "coef_to_kg", mode="after")
    @classmethod
    def validate_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


class PurchaseModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.purchase
    registration_keys = [
        DataEntryTypeEnum.scientific_equipment,
        DataEntryTypeEnum.it_equipment,
        DataEntryTypeEnum.consumable_accessories,
        DataEntryTypeEnum.biological_chemical_gaseous_product,
        DataEntryTypeEnum.services,
        DataEntryTypeEnum.vehicles,
        DataEntryTypeEnum.other_purchases,
    ]

    create_dto = PurchaseHandlerCreate
    update_dto = PurchaseHandlerUpdate
    response_dto = PurchaseHandlerResponse

    kind_field: str = "purchase_institutional_code"
    kind_label_field: str = "purchase_institutional_description"
    subkind_field: Optional[str] = ""
    # purchase_institutional_code is not always present, so we can't 100% rely on it
    # for matching entries to factors
    # it's Optional in create_dto and update_dto, and some entries
    # may have it missing or null in csv
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        "name": DataEntry.data["name"].as_string(),
        "supplier": DataEntry.data["supplier"].as_string(),
        "quantity": DataEntry.data["quantity"].as_float(),
        "total_spent_amount": DataEntry.data["total_spent_amount"].as_float(),
        "purchase_institutional_code": DataEntry.data[
            "purchase_institutional_code"
        ].as_string(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "name": DataEntry.data["name"].as_string(),
        "supplier": DataEntry.data["supplier"].as_string(),
        "purchase_institutional_code": DataEntry.data[
            "purchase_institutional_code"
        ].as_string(),
    }

    def to_response(self, data_entry: DataEntry) -> PurchaseHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                **data_entry.data,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                "name": data_entry.data.get("name"),
                "supplier": data_entry.data.get("supplier"),
                "quantity": data_entry.data.get("quantity"),
                "purchase_institutional_code": data_entry.data.get(
                    "purchase_institutional_code"
                ),
                "purchase_institutional_description": data_entry.data.get(
                    "purchase_institutional_description"
                ),
                "total_spent_amount": data_entry.data.get("total_spent_amount"),
                "kg_co2eq": data_entry.data.get("kg_co2eq", None),
            }
        )

    def validate_create(self, payload: dict) -> PurchaseHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> PurchaseHandlerUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []
        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                formula_key="ef_kg_co2eq_per_currency",
                quantity_key="total_spent_amount",
            )
        ]


class PurchaseAdditionalModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.purchase
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.additional_purchases

    create_dto = PurchaseAdditionalHandlerCreate
    update_dto = PurchaseAdditionalHandlerUpdate
    response_dto = PurchaseAdditionalHandlerResponse

    kind_field: str = "name"
    subkind_field: Optional[str] = ""

    sort_map = {
        "id": DataEntry.id,
        "name": DataEntry.data["name"].as_string(),
        "unit": DataEntry.data["unit"].as_string(),
        "annual_consumption": DataEntry.data["annual_consumption"].as_float(),
        "coef_to_kg": DataEntry.data["coef_to_kg"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "name": DataEntry.data["name"].as_string(),
        "unit": DataEntry.data["unit"].as_string(),
    }

    def to_response(self, data_entry: DataEntry) -> PurchaseAdditionalHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
            }
        )

    def validate_create(self, payload: dict) -> PurchaseAdditionalHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> PurchaseAdditionalHandlerUpdate:
        return self.update_dto.model_validate(payload)

    def resolve_computations(self, data_entry, emission_type, ctx: dict) -> list:

        factor_id = ctx.get("primary_factor_id")
        if factor_id is None:
            return []

        def _additional_purchase_formula(ctx: dict, factor_values: dict):
            annual_consumption = ctx.get("annual_consumption", 0)
            coef_to_kg = ctx.get("coef_to_kg", 0)
            ef = factor_values.get("ef_kg_co2eq_per_kg", 0)
            if annual_consumption is None or coef_to_kg is None or ef is None:
                return None
            return annual_consumption * coef_to_kg * ef

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_id=int(factor_id),
                formula_func=_additional_purchase_formula,
            )
        ]


## PURCHASE FACTOR HANDLERS

# --- Additional Purchases ---

purchase_additional_classification_fields: list[str] = ["name"]
purchase_additional_value_fields: list[str] = ["ef_kg_co2eq_per_kg"]


class PurchaseAdditionalFactorCreate(FactorCreate):
    name: str
    ef_kg_co2eq_per_kg: float

    @field_validator("ef_kg_co2eq_per_kg", mode="after")
    @classmethod
    def validate_ef(cls, v: float) -> float:
        if v < 0:
            raise ValueError("ef_kg_co2eq_per_kg must be non-negative")
        return v


class PurchaseAdditionalFactorUpdate(FactorUpdate):
    name: Optional[str] = None
    ef_kg_co2eq_per_kg: Optional[float] = None

    @field_validator("ef_kg_co2eq_per_kg", mode="after")
    @classmethod
    def validate_ef(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("ef_kg_co2eq_per_kg must be non-negative")
        return v


class PurchaseAdditionalFactorResponse(FactorResponseGen):
    name: str
    ef_kg_co2eq_per_kg: float


class PurchaseAdditionalFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum | None = None
    registration_keys = [DataEntryTypeEnum.additional_purchases]
    emission_type = EmissionType.purchases__additional

    create_dto = PurchaseAdditionalFactorCreate
    update_dto = PurchaseAdditionalFactorUpdate
    response_dto = PurchaseAdditionalFactorResponse

    classification_fields: list[str] = purchase_additional_classification_fields
    value_fields: list[str] = purchase_additional_value_fields


# --- Common Purchases (7 types, same CSV format) ---

purchase_common_classification_fields: list[str] = [
    "purchase_institutional_code",
    "purchase_institutional_description",
    "purchase_additional_code",
    "currency",
]
purchase_common_value_fields: list[str] = ["ef_kg_co2eq_per_currency"]


class PurchaseCommonFactorCreate(FactorCreate):
    purchase_institutional_code: str
    purchase_institutional_description: Optional[str] = None
    purchase_additional_code: str
    purchase_category: str
    currency: str
    ef_kg_co2eq_per_currency: float

    @field_validator("ef_kg_co2eq_per_currency", mode="after")
    @classmethod
    def validate_ef(cls, v: float) -> float:
        if v < 0:
            raise ValueError("ef_kg_co2eq_per_currency must be non-negative")
        return v


class PurchaseCommonFactorUpdate(FactorUpdate):
    purchase_institutional_code: Optional[str] = None
    purchase_institutional_description: Optional[str] = None
    purchase_additional_code: Optional[str] = None
    currency: Optional[str] = None
    ef_kg_co2eq_per_currency: Optional[float] = None


class PurchaseCommonFactorResponse(FactorResponseGen):
    purchase_institutional_code: str
    purchase_institutional_description: Optional[str] = None
    purchase_additional_code: Optional[str] = None
    currency: str
    ef_kg_co2eq_per_currency: Optional[float] = None


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
    emission_type = None  # resolved per type via DATA_ENTRY_TO_EMISSION_TYPES

    create_dto = PurchaseCommonFactorCreate
    update_dto = PurchaseCommonFactorUpdate
    response_dto = PurchaseCommonFactorResponse

    classification_fields: list[str] = purchase_common_classification_fields
    value_fields: list[str] = purchase_common_value_fields
