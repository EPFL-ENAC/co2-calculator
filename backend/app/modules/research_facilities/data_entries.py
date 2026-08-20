"""Research Facilities data-entry schemas (common + animal)."""

from pydantic import ValidationInfo, field_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class ResearchFacilitiesCommonHandlerResponse(DataEntryResponseGen):
    researchfacility_id: str | None = None
    researchfacility_name: str | None = None
    use: float | None = None
    use_unit: str | None = None
    note: str | None = None
    kg_co2eq: float | None = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v)


class ResearchFacilitiesCommonHandlerCreate(DataEntryCreate):
    researchfacility_id: str
    researchfacility_name: str
    use: float
    use_unit: str
    note: str | None = None
    kg_co2eq: float | None = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> str | None:
        if v is None:
            raise ValueError("researchfacility_id is required")
        return str(v)

    @field_validator("researchfacility_name", mode="before")
    @classmethod
    def _validate_researchfacility_name_response(cls, v: object) -> str | None:
        if v is None:
            raise ValueError("researchfacility_name is required")
        return str(v)

    @field_validator("use", mode="before")
    @classmethod
    def _validate_use_response(cls, v: object) -> float | None:
        if v is None:
            raise ValueError("use is required")
        if not isinstance(v, (int, float)):
            raise ValueError("use must be a number")
        if v < 0:
            raise ValueError("use must be a positive number or zero")
        return float(v)

    @field_validator(
        "researchfacility_id", "researchfacility_name", "use_unit", mode="after"
    )
    @classmethod
    def _non_empty(cls, v: str, info: ValidationInfo) -> str:
        if not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return v


class ResearchFacilitiesCommonHandlerUpdate(DataEntryUpdate):
    researchfacility_id: str | None = None
    researchfacility_name: str | None = None
    use: float | None = None
    use_unit: str | None = None
    note: str | None = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> str | None:
        if v is None:
            return None
        return str(v)

    @field_validator("use", mode="before")
    @classmethod
    def _validate_use(cls, v: object) -> float | None:
        if v is None:
            return None
        if not isinstance(v, (int, float)):
            raise ValueError("use must be a number")
        if v < 0:
            raise ValueError("use must be a positive number or zero")
        return float(v)

    @field_validator(
        "researchfacility_id", "researchfacility_name", "use_unit", mode="after"
    )
    @classmethod
    def _non_empty(cls, v: str | None, info: ValidationInfo) -> str | None:
        if v is not None and not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return v


class ResearchFacilitiesAnimalHandlerResponse(DataEntryResponseGen):
    researchfacility_id: str | None = None
    researchfacility_name: str | None = None
    researchfacility_type: str | None = None
    use: float | None = None
    use_unit: str | None = None
    note: str | None = None
    kg_co2eq: float | None = None


class ResearchFacilitiesAnimalHandlerCreate(DataEntryCreate):
    researchfacility_id: str
    researchfacility_name: str
    researchfacility_type: str
    use: float
    use_unit: str
    note: str | None = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id(cls, v: object) -> str | None:
        if v is None:
            raise ValueError("researchfacility_id is required")
        return str(v)

    @field_validator("use", mode="before")
    @classmethod
    def _validate_use(cls, v: object) -> float | None:
        if v is None:
            raise ValueError("use is required")
        if not isinstance(v, (int, float)):
            raise ValueError("use must be a number")
        if v < 0:
            raise ValueError("use must be a positive number or zero")
        return float(v)

    @field_validator(
        "researchfacility_id",
        "researchfacility_name",
        "researchfacility_type",
        "use_unit",
        mode="after",
    )
    @classmethod
    def _non_empty(cls, v: str, info: ValidationInfo) -> str:
        if not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return v


class ResearchFacilitiesAnimalHandlerUpdate(DataEntryUpdate):
    researchfacility_id: str | None = None
    researchfacility_name: str | None = None
    researchfacility_type: str | None = None
    use: float | None = None
    use_unit: str | None = None
    note: str | None = None

    @field_validator("use", mode="before")
    @classmethod
    def _validate_use(cls, v: object) -> float | None:
        if v is None:
            return None
        if not isinstance(v, (int, float)):
            raise ValueError("use must be a number")
        if v < 0:
            raise ValueError("use must be a positive number or zero")
        return float(v)

    @field_validator(
        "researchfacility_id",
        "researchfacility_name",
        "researchfacility_type",
        "use_unit",
        mode="after",
    )
    @classmethod
    def _non_empty(cls, v: str | None, info: ValidationInfo) -> str | None:
        if v is not None and not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return v
