"""Research Facilities data-entry schemas (common + animal)."""

from typing import Optional

from pydantic import field_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class ResearchFacilitiesCommonHandlerResponse(DataEntryResponseGen):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    use: Optional[float] = None
    use_unit: Optional[str] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class ResearchFacilitiesCommonHandlerCreate(DataEntryCreate):
    researchfacility_id: str
    researchfacility_name: str
    use: float
    use_unit: str
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> Optional[str]:
        if v is None:
            raise ValueError("researchfacility_id is required")
        return str(v)

    @field_validator("researchfacility_name", mode="before")
    @classmethod
    def _validate_researchfacility_name_response(cls, v: object) -> Optional[str]:
        if v is None:
            raise ValueError("researchfacility_name is required")
        return str(v)

    @field_validator("use", mode="before")
    @classmethod
    def _validate_use_response(cls, v: object) -> Optional[float]:
        if v is None:
            raise ValueError("use is required")
        if not isinstance(v, (int, float)):
            raise ValueError("use must be a number")
        if v < 0:
            raise ValueError("use must be a positive number or zero")
        return float(v)

    # TODO: validation for use_unit: it was not done!


class ResearchFacilitiesCommonHandlerUpdate(DataEntryUpdate):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    use: Optional[float] = None
    use_unit: Optional[str] = None
    note: Optional[str] = None

    @field_validator("researchfacility_id", mode="before")
    @classmethod
    def _validate_researchfacility_id_response(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class ResearchFacilitiesAnimalHandlerResponse(DataEntryResponseGen):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    researchfacility_type: Optional[str] = None
    use: Optional[float] = None
    use_unit: Optional[str] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class ResearchFacilitiesAnimalHandlerCreate(DataEntryCreate):
    researchfacility_id: str
    researchfacility_name: str
    researchfacility_type: str
    use: float
    use_unit: str
    note: Optional[str] = None


class ResearchFacilitiesAnimalHandlerUpdate(DataEntryUpdate):
    researchfacility_id: Optional[str] = None
    researchfacility_name: Optional[str] = None
    researchfacility_type: Optional[str] = None
    use: Optional[float] = None
    use_unit: Optional[str] = None
    note: Optional[str] = None
