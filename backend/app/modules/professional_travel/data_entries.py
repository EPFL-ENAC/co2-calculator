from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class TrainCabinClassValidationMixin:
    @field_validator("cabin_class", mode="after")
    @classmethod
    def validate_cabin_class(cls, v: Optional[str]) -> Optional[str]:
        valid_classes = ["first", "second"]
        if v is not None and v.lower() not in valid_classes:
            raise ValueError(
                f"Invalid cabin class '{v}', must be one of {valid_classes}"
            )
        return v.lower() if v else None


class PlaneCabinClassValidationMixin:
    @field_validator("cabin_class", mode="after")
    @classmethod
    def validate_cabin_class(cls, v: Optional[str]) -> Optional[str]:
        valid_classes = ["first", "business", "economy"]
        if v is not None and v.lower() not in valid_classes:
            raise ValueError(
                f"Invalid cabin class '{v}', must be one of {valid_classes}"
            )
        return v.lower() if v else None


class DepartureDateMixin(BaseModel):
    """Mixin for parsing departure_date from various formats."""

    @field_validator("departure_date", mode="before", check_fields=False)
    @classmethod
    def parse_departure_date(cls, v: Any) -> Optional[date]:
        if v is None:
            return None
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            if not v.strip():
                return None
            normalized = v.replace("/", "-")
            try:
                return datetime.fromisoformat(normalized.replace("Z", "+00:00")).date()
            except ValueError:
                return date.fromisoformat(normalized)
        return v


class ProfessionalTravelPlaneHandlerResponse(DepartureDateMixin, DataEntryResponseGen):
    user_institutional_id: str
    origin_iata: str
    destination_iata: str
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    origin: Optional[str] = None
    destination: Optional[str] = None
    origin_name: Optional[str] = None
    destination_name: Optional[str] = None
    distance_km: Optional[float] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class ProfessionalTravelTrainHandlerResponse(DepartureDateMixin, DataEntryResponseGen):
    user_institutional_id: str
    origin_name: str
    destination_name: str
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    origin: Optional[str] = None
    destination: Optional[str] = None
    distance_km: Optional[float] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None


class ProfessionalTravelPlaneHandlerCreate(
    PlaneCabinClassValidationMixin, DepartureDateMixin, DataEntryCreate
):
    origin_iata: str  ## IATA code
    destination_iata: str  ## IATA code
    user_institutional_id: str
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    cabin_class: str
    note: Optional[str] = None
    # __kg_co2eq_override__ for kg_co2eq

    @field_validator("number_of_trips", mode="after")
    @classmethod
    def validate_number_of_trips(cls, v: int) -> int:
        if v < 1:
            raise ValueError("number_of_trips must be at least 1")
        return v


class ProfessionalTravelTrainHandlerCreate(
    TrainCabinClassValidationMixin, DepartureDateMixin, DataEntryCreate
):
    user_institutional_id: str
    origin_name: str
    destination_name: str
    # check if necessary after migration to new reference location for train
    origin_natural_key: Optional[str] = None
    destination_natural_key: Optional[str] = None
    # Required for CSV rows lacking a precomputed ``*_natural_key``: the
    # ingest-time resolver uses them to scope same-name stations to one
    # country (e.g. Bern, CH vs Berne, DE). Optional at the schema level
    # because UI/API rows resolve via ``*_natural_key`` instead; the CSV
    # resolver (``enrich_csv_row``) rejects rows that supply neither.
    origin_country_code: str
    destination_country_code: str
    departure_date: Optional[date] = None
    number_of_trips: int = 1
    cabin_class: str
    note: Optional[str] = None
    # __kg_co2eq_override__ for kg_co2eq

    @field_validator("number_of_trips", mode="after")
    @classmethod
    def validate_number_of_trips(cls, v: int) -> int:
        if v < 1:
            raise ValueError("number_of_trips must be at least 1")
        return v


class ProfessionalTravelPlaneHandlerUpdate(DepartureDateMixin, DataEntryUpdate):
    # traveler_name: Optional[str] = None
    # traveler_id: Optional[int] = None
    origin_iata: Optional[str] = None
    destination_iata: Optional[str] = None
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: Optional[int] = None
    note: Optional[str] = None


class ProfessionalTravelTrainHandlerUpdate(DepartureDateMixin, DataEntryUpdate):
    # traveler_name: Optional[str] = None
    # traveler_id: Optional[int] = None
    origin_name: Optional[str] = None
    destination_name: Optional[str] = None
    origin_natural_key: Optional[str] = None
    destination_natural_key: Optional[str] = None
    cabin_class: Optional[str] = None
    departure_date: Optional[date] = None
    number_of_trips: Optional[int] = None
    note: Optional[str] = None
