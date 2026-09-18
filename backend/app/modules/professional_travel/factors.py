from collections.abc import Iterable

from pydantic import ValidationInfo, field_validator

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.modules.emissions import EmissionType
from app.modules.professional_travel.emissions import PLANE_CABIN_MAP
from app.schemas.factor import (
    BaseFactorHandler,
    FactorCreate,
    FactorResponseGen,
    FactorUpdate,
)
from app.schemas.fields import ROW_COUNTRY_CODE, ClassificationKey, CountryCode

# Closed vocabulary (#2588): the haul categories the shipped plane factor CSV
# carries. ``get_haul_category`` picks one by distance band, so a category
# outside this list is a band no trip can ever fall into.
PLANE_HAUL_CATEGORIES: list[str] = ["short_to_medium_haul", "medium_to_long_haul"]


def _validate_non_negative_float(v: float | None, field_name: str) -> float | None:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


def check_plane_distance_bands(factors: Iterable[Factor]) -> None:
    """Reject plane factors whose ``[min, max)`` bands overlap within a cabin class.

    ``get_haul_category`` returns the first band a distance falls into, so two
    overlapping bands would make the resolved factor depend on row order.
    Raises ``ValueError`` naming the two categories that collide (#2588).
    """
    bands_by_cabin: dict[str, list[tuple[float, float, str]]] = {}
    for factor in factors:
        classification = factor.classification or {}
        values = factor.values or {}
        bands_by_cabin.setdefault(str(classification.get("cabin_class")), []).append(
            (
                float(values["min_distance"]),
                float(values["max_distance"]),
                str(classification.get("category")),
            )
        )
    for cabin_class, bands in bands_by_cabin.items():
        bands.sort()
        for (_, prev_max, prev_cat), (cur_min, _, cur_cat) in zip(
            bands, bands[1:], strict=False
        ):
            if cur_min < prev_max:
                raise ValueError(
                    f"Plane factor distance bands overlap for cabin class "
                    f"'{cabin_class}': '{prev_cat}' and '{cur_cat}'"
                )


class TravelPlaneBase:
    category: ClassificationKey
    cabin_class: str
    ef_kg_co2eq_per_km: float
    rfi_adjustment: float
    min_distance: float
    max_distance: float


class _TravelPlaneBaseValidationMixin:
    @field_validator(
        "ef_kg_co2eq_per_km",
        "rfi_adjustment",
        "min_distance",
        "max_distance",
        mode="after",
    )
    @classmethod
    def validate_factor_non_negative(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        return _validate_non_negative_float(v, info.field_name or "")

    @field_validator("cabin_class", mode="after")
    @classmethod
    def validate_cabin_class(cls, v: str) -> str:
        # Same normalization as the entry-side cabin-class mixins: the two
        # sides join on this key with exact string equality (#1489).
        normalized = v.strip().lower()
        if not normalized:
            raise ValueError("Cabin class is required")
        if normalized not in PLANE_CABIN_MAP:
            raise ValueError("Invalid cabin class")
        return normalized

    @field_validator("category", mode="after")
    @classmethod
    def validate_category(cls, v: str) -> str:
        normalized = v.lower()
        if normalized not in PLANE_HAUL_CATEGORIES:
            raise ValueError(
                f"category must be one of: {', '.join(PLANE_HAUL_CATEGORIES)}"
            )
        return normalized

    @field_validator("max_distance", mode="after")
    @classmethod
    def validate_distance_band(cls, v: float, info: ValidationInfo) -> float:
        # min_distance is declared first, so it is already validated here.
        if v <= info.data["min_distance"]:
            raise ValueError("max_distance must be greater than min_distance")
        return v


class TravelPlaneFactorResponse(
    FactorResponseGen, TravelPlaneBase, _TravelPlaneBaseValidationMixin
):
    pass


class TravelPlaneFactorCreate(
    FactorCreate, TravelPlaneBase, _TravelPlaneBaseValidationMixin
):
    pass


class TravelPlaneFactorUpdate(
    FactorUpdate, TravelPlaneBase, _TravelPlaneBaseValidationMixin
):
    pass


class TravelPlaneFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.plane
    registration_keys = [DataEntryTypeEnum.plane]
    emission_type: EmissionType = EmissionType.professional_travel__plane

    classification_fields: list[str] = ["category", "cabin_class"]
    value_fields: list[str] = [
        "ef_kg_co2eq_per_km",
        "rfi_adjustment",
        "min_distance",
        "max_distance",
    ]

    create_dto = TravelPlaneFactorCreate
    update_dto = TravelPlaneFactorUpdate
    response_dto = TravelPlaneFactorResponse

    def validate_year_factors(self, factors: list[Factor]) -> None:
        check_plane_distance_bands(factors)


class TravelTrainBase:
    country_code: CountryCode
    ef_kg_co2eq_per_km: float


class _TravelTrainBaseValidationMixin:
    @field_validator(
        "ef_kg_co2eq_per_km",
        mode="after",
    )
    @classmethod
    def validate_factor_non_negative(
        cls, v: float | None, info: ValidationInfo
    ) -> float | None:
        return _validate_non_negative_float(v, info.field_name or "")

    @field_validator("country_code", mode="after")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        # in ISO 3166-1 alpha-2 format or use RoW for rest of the world
        # for now we check two letter format but we don't validate against
        # a list of actual country codes (CountryCode already normalized case)
        if v != ROW_COUNTRY_CODE and (len(v) != 2 or not v.isalpha()):
            raise ValueError(
                "Invalid country code, must be ISO 3166-1 alpha-2 or 'RoW'"
            )
        return v


class TravelTrainFactorResponse(
    FactorResponseGen, TravelTrainBase, _TravelTrainBaseValidationMixin
):
    pass


class TravelTrainFactorCreate(
    FactorCreate, TravelTrainBase, _TravelTrainBaseValidationMixin
):
    pass


class TravelTrainFactorUpdate(
    FactorUpdate, TravelTrainBase, _TravelTrainBaseValidationMixin
):
    pass


class TravelTrainFactorHandler(BaseFactorHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.train
    emission_type: EmissionType = EmissionType.professional_travel__train

    registration_keys = [DataEntryTypeEnum.train]

    classification_fields: list[str] = ["country_code"]
    value_fields: list[str] = ["ef_kg_co2eq_per_km"]

    create_dto = TravelTrainFactorCreate
    update_dto = TravelTrainFactorUpdate
    response_dto = TravelTrainFactorResponse
