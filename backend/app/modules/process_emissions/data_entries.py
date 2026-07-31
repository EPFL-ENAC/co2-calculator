from pydantic import field_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class ProcessEmissionsHandlerResponse(DataEntryResponseGen):
    category: str
    subcategory: str | None = None
    quantity: float
    note: str | None = None
    kg_co2eq: float | None = None


class ProcessEmissionsHandlerCreate(DataEntryCreate):
    category: str
    subcategory: str | None = None
    quantity: float
    note: str | None = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Quantity must be non-negative")
        return v


class ProcessEmissionsHandlerUpdate(DataEntryUpdate):
    category: str | None = None
    subcategory: str | None = None
    quantity: float | None = None
    note: str | None = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Quantity must be non-negative")
        return v
