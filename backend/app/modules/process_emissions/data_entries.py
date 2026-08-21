from pydantic import ValidationInfo, field_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class ProcessEmissionsHandlerResponse(DataEntryResponseGen):
    category: str
    subcategory: str | None = None
    quantity_kg: float
    note: str | None = None
    kg_co2eq: float | None = None


class ProcessEmissionsHandlerCreate(DataEntryCreate):
    category: str
    subcategory: str | None = None
    quantity_kg: float
    note: str | None = None

    @field_validator("category", mode="after")
    @classmethod
    def _non_empty(cls, v: str, info: ValidationInfo) -> str:
        if not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return v

    @field_validator("quantity_kg", mode="after")
    @classmethod
    def validate_quantity_kg(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Quantity must be non-negative")
        return v


class ProcessEmissionsHandlerUpdate(DataEntryUpdate):
    category: str | None = None
    subcategory: str | None = None
    quantity_kg: float | None = None
    note: str | None = None

    @field_validator("category", mode="after")
    @classmethod
    def _non_empty(cls, v: str | None, info: ValidationInfo) -> str | None:
        if v is not None and not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return v

    @field_validator("quantity_kg", mode="after")
    @classmethod
    def validate_quantity_kg(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Quantity must be non-negative")
        return v
