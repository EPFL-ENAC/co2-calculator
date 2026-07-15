from typing import Optional

from pydantic import field_validator

from app.modules.headcount import SIUS_CODE_VALUES
from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


def _validate_sius_code(v: str) -> str:
    if v not in SIUS_CODE_VALUES:
        allowed_values = ", ".join(sorted(SIUS_CODE_VALUES))
        raise ValueError(f"sius_code must be one of: {allowed_values}")
    return v


def _validate_fte(v: float) -> float:
    # Aggregate FTE for a whole category — unlike the Calculator's
    # per-person entries, values above 1 are expected.
    if v < 0:
        raise ValueError("FTE must be at least 0")
    return v


class PlannerHeadCountResponse(DataEntryResponseGen):
    sius_code: str
    fte: Optional[float] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class PlannerHeadCountCreate(DataEntryCreate):
    sius_code: str
    fte: float
    note: Optional[str] = None

    @field_validator("sius_code", mode="after")
    @classmethod
    def validate_sius_code(cls, v: str) -> str:
        return _validate_sius_code(v)

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: float) -> float:
        return _validate_fte(v)


class PlannerHeadCountUpdate(DataEntryUpdate):
    sius_code: Optional[str] = None
    fte: Optional[float] = None
    note: Optional[str] = None

    @field_validator("sius_code", mode="after")
    @classmethod
    def validate_sius_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_sius_code(v)

    @field_validator("fte", mode="after")
    @classmethod
    def validate_fte(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        return _validate_fte(v)
