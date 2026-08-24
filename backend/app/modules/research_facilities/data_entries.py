"""Research Facilities data-entry schemas (common + animal)."""

from dataclasses import dataclass
from functools import lru_cache

from pydantic import ValidationInfo, field_validator, model_validator

from app.core.config import get_settings
from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)


@dataclass(frozen=True)
class UseBounds:
    """Upper bound and granularity of `use` for one `use_unit`."""

    maximum: float | None = None
    integer_only: bool = False


# #2007 — `use` measures a different quantity per platform and the factor's
# `use_unit` names which: a share of the platform (%), machine time (hours),
# spend (CHF), or animal housings. The factor carries no min/max, so the
# bounds are hardcoded here and mirrored in the frontend module config. A unit
# absent from this table is simply unbounded above — another institution may
# use one this deployment has never seen.
@lru_cache(maxsize=1)
def use_bounds() -> dict[str, UseBounds]:
    """Built once, lazily: the hours ceiling comes from settings, and reading
    config at import time would pin it before the environment is loaded.
    """
    settings = get_settings()
    return {
        "%": UseBounds(maximum=100),
        # The same hours-in-a-year the equipment module computes with, so a
        # future deployment overriding either knob moves both together.
        "hours": UseBounds(maximum=settings.HOURS_PER_WEEK * settings.WEEKS_PER_YEAR),
        "CHF": UseBounds(),
        "housings": UseBounds(integer_only=True),
    }


def validate_use_within_unit_bounds(use: float | None, use_unit: str | None) -> None:
    """Reject a `use` its unit makes impossible — 150%, half an animal housing.

    Raises rather than clamping: a wrong total that looks complete is worse
    than a blocked save, and `use` divides straight into the platform's
    footprint.
    """
    if use is None or use_unit is None:
        return
    bounds = use_bounds().get(use_unit)
    if bounds is None:
        return
    if bounds.maximum is not None and use > bounds.maximum:
        raise ValueError(
            f"use must be at most {bounds.maximum:g} when the unit is '{use_unit}'"
        )
    if bounds.integer_only and use != int(use):
        raise ValueError(f"use must be a whole number when the unit is '{use_unit}'")


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

    @model_validator(mode="after")
    def _use_within_unit_bounds(self) -> ResearchFacilitiesCommonHandlerCreate:
        validate_use_within_unit_bounds(self.use, self.use_unit)
        return self


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

    @model_validator(mode="after")
    def _use_within_unit_bounds(self) -> ResearchFacilitiesCommonHandlerUpdate:
        validate_use_within_unit_bounds(self.use, self.use_unit)
        return self


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

    @model_validator(mode="after")
    def _use_within_unit_bounds(self) -> ResearchFacilitiesAnimalHandlerCreate:
        validate_use_within_unit_bounds(self.use, self.use_unit)
        return self


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

    @model_validator(mode="after")
    def _use_within_unit_bounds(self) -> ResearchFacilitiesAnimalHandlerUpdate:
        validate_use_within_unit_bounds(self.use, self.use_unit)
        return self
