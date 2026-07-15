from typing import Optional

from pydantic import field_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class ProcessEmissionsHandlerResponse(DataEntryResponseGen):
    category: str
    subcategory: Optional[str] = None
    quantity: float
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class ProcessEmissionsHandlerCreate(DataEntryCreate):
    category: str
    subcategory: Optional[str] = None
    quantity: float
    note: Optional[str] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Quantity must be non-negative")
        return v


class ProcessEmissionsHandlerUpdate(DataEntryUpdate):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    quantity: Optional[float] = None
    note: Optional[str] = None

    @field_validator("quantity", mode="after")
    @classmethod
    def validate_quantity(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Quantity must be non-negative")
        return v
