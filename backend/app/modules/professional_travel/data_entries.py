from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


class TrainCabinClassValidationMixin:
    @field_validator("cabin_class", mode="after")
    @classmethod
    def validate_cabin_class(cls, v: str | None) -> str | None:
        valid_classes = ["first", "second"]
        if v is not None and v.lower() not in valid_classes:
            raise ValueError(
                f"Invalid cabin class '{v}', must be one of {valid_classes}"
            )
        return v.lower() if v else None


class PlaneCabinClassValidationMixin:
    @field_validator("cabin_class", mode="after")
    @classmethod
    def validate_cabin_class(cls, v: str | None) -> str | None:
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
    def parse_departure_date(cls, v: Any) -> date | None:
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
    user_institutional_id: str | None
    origin_iata: str
    destination_iata: str
    cabin_class: str | None = None
    departure_date: date | None = None
    number_of_trips: int = 1
    origin: str | None = None
    destination: str | None = None
    origin_name: str | None = None
    destination_name: str | None = None
    distance_km: float | None = None
    note: str | None = None
    kg_co2eq: float | None = None


class ProfessionalTravelTrainHandlerResponse(DepartureDateMixin, DataEntryResponseGen):
    user_institutional_id: str | None
    origin_name: str
    destination_name: str
    cabin_class: str | None = None
    departure_date: date | None = None
    number_of_trips: int = 1
    origin: str | None = None
    destination: str | None = None
    distance_km: float | None = None
    note: str | None = None
    kg_co2eq: float | None = None


class ProfessionalTravelPlaneHandlerCreate(
    PlaneCabinClassValidationMixin, DepartureDateMixin, DataEntryCreate
):
    origin_iata: str  ## IATA code
    destination_iata: str  ## IATA code
    user_institutional_id: str | None
    departure_date: date | None = None
    number_of_trips: int = 1
    cabin_class: str
    note: str | None = None
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
    user_institutional_id: str | None
    origin_name: str
    destination_name: str
    # Optional here (unlike plane's origin_iata) because CSV rows validate
    # before enrich_csv_row resolves the natural_key from origin_name +
    # origin_country_code (#1183). The API path has no such staging: a
    # missing natural_key there is rejected in
    # CarbonReportModuleWorkflow.create (#1186), not by this DTO.
    origin_natural_key: str | None = None
    destination_natural_key: str | None = None
    # Required for CSV rows lacking a precomputed ``*_natural_key``: the
    # ingest-time resolver uses them to scope same-name stations to one
    # country (e.g. Bern, CH vs Berne, DE). Optional at the schema level
    # because UI/API rows resolve via ``*_natural_key`` instead; the CSV
    # resolver (``enrich_csv_row``) rejects rows that supply neither.
    origin_country_code: str
    destination_country_code: str
    departure_date: date | None = None
    number_of_trips: int = 1
    cabin_class: str
    note: str | None = None
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
    origin_iata: str | None = None
    destination_iata: str | None = None
    cabin_class: str | None = None
    departure_date: date | None = None
    number_of_trips: int | None = None
    note: str | None = None


class ProfessionalTravelTrainHandlerUpdate(DepartureDateMixin, DataEntryUpdate):
    # traveler_name: Optional[str] = None
    # traveler_id: Optional[int] = None
    origin_name: str | None = None
    destination_name: str | None = None
    origin_natural_key: str | None = None
    destination_natural_key: str | None = None
    cabin_class: str | None = None
    departure_date: date | None = None
    number_of_trips: int | None = None
    note: str | None = None
