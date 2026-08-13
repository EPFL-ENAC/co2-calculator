from pydantic import BaseModel, field_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)

SIUS_CODE_VALUES = {"51", "52", "53", "54", "56", "57", "58", "59"}


class HeadcountItemResponse(DataEntryResponseGen):
    name: str
    sius_code: str | None = None
    fte: float | None = None
    user_institutional_id: str | None = None
    note: str | None = None


class HeadCountStudentResponse(DataEntryResponseGen):
    fte: float | None = None


class HeadCountCreate(DataEntryCreate):
    name: str
    sius_code: str
    user_institutional_id: str
    fte: float
    note: str | None = None

    @field_validator("name", mode="after")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("user_institutional_id", mode="before")
    @classmethod
    def validate_user_institutional_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("User institutional ID cannot be empty")
        # doc says numbers only but user can use letters as well (test-412424 e.g)
        return v.strip()

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v > 1:
            raise ValueError("FTE cannot exceed 1")
        if v < 0:
            raise ValueError("FTE must be at least 0")
        return v

    @field_validator("sius_code", mode="after")
    @classmethod
    def validate_sius_code(cls, v: str) -> str:
        if v not in SIUS_CODE_VALUES:
            allowed_values = ", ".join(sorted(SIUS_CODE_VALUES))
            raise ValueError(f"sius_code must be one of: {allowed_values}")
        return v


class HeadCountStudentCreate(DataEntryCreate):
    fte: float

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: float) -> float:
        if v < 0:
            raise ValueError("FTE must be at least 0")
        return v


class HeadCountStudentUpdate(DataEntryUpdate):
    fte: float | None = None

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < 0:
            raise ValueError("FTE must be at least 0")
        return v


class HeadCountUpdate(DataEntryUpdate):
    name: str | None = None
    sius_code: str | None = None
    # #951: SCIPER is updatable — only on a user-created row (enforced by
    # the data-entry-permissions layer, not here; this DTO just needs to
    # accept the field at all).
    user_institutional_id: str | None = None
    fte: float | None = None
    note: str | None = None

    @field_validator("user_institutional_id", mode="before")
    @classmethod
    def validate_user_institutional_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("User institutional ID cannot be empty")
        return v.strip()

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v > 1:
            raise ValueError("FTE cannot exceed 1")
        if v < 0:
            raise ValueError("FTE must be at least 0")
        return v

    @field_validator("sius_code", mode="after")
    @classmethod
    def validate_sius_code(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SIUS_CODE_VALUES:
            allowed_values = ", ".join(sorted(SIUS_CODE_VALUES))
            raise ValueError(f"sius_code must be one of: {allowed_values}")
        return v


class HeadcountMemberDropdownItem(BaseModel):
    """Lightweight member record used to populate traveler dropdowns."""

    institutional_id: str
    name: str
