from typing import Optional, Self

from pydantic import ValidationInfo, field_validator, model_validator

from app.schemas.data_entry import (
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)

MAX_WEEKLY_USAGE_HOURS = 168


def _validate_weekly_usage_hours(v: Optional[int]) -> Optional[int]:
    if v is None:
        return v
    if v < 0:
        raise ValueError("Usage hours must be non-negative")
    if v > MAX_WEEKLY_USAGE_HOURS:
        raise ValueError(
            f"Usage hours cannot exceed {MAX_WEEKLY_USAGE_HOURS} hours per week"
        )
    return v


def _validate_non_negative_float(
    v: Optional[float], field_name: str
) -> Optional[float]:
    if v is None:
        return v
    if v < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return v


class _EquipmentUsageHoursValidationMixin:
    active_usage_hours_per_week: Optional[int]
    standby_usage_hours_per_week: Optional[int]

    @field_validator(
        "active_usage_hours_per_week", "standby_usage_hours_per_week", mode="after"
    )
    @classmethod
    def validate_usage_hours(cls, v: Optional[int]) -> Optional[int]:
        return _validate_weekly_usage_hours(v)

    @model_validator(mode="after")
    def validate_total_usage_hours(self) -> Self:
        active_hours = self.active_usage_hours_per_week
        standby_hours = self.standby_usage_hours_per_week
        if active_hours is not None and standby_hours is not None:
            if active_hours + standby_hours > MAX_WEEKLY_USAGE_HOURS:
                raise ValueError(
                    "The sum of active_usage_hours_per_week and "
                    "standby_usage_hours_per_week must be <= 168"
                )
        return self


# https://epfl-enac.github.io/co2-calculator-back-office-doc/data-description/#equipment
class EquipmentHandlerResponse(DataEntryResponseGen):
    name: str
    equipment_class: str
    sub_class: Optional[str] = None
    active_usage_hours_per_week: Optional[int] = None
    standby_usage_hours_per_week: Optional[int] = None
    note: Optional[str] = None
    kg_co2eq: Optional[float] = None
    active_power_w: Optional[int] = None
    standby_power_w: Optional[int] = None


class EquipmentHandlerCreate(_EquipmentUsageHoursValidationMixin, DataEntryCreate):
    equipment_id: str
    name: str
    equipment_class: str
    sub_class: Optional[str] = None
    active_usage_hours_per_week: Optional[int] = None
    standby_usage_hours_per_week: Optional[int] = None
    note: Optional[str] = None
    # kg_co2eq: Optional[float] = None  # from csv is __kg_co2eq_override__

    @field_validator("equipment_id", "name", "equipment_class", mode="after")
    @classmethod
    def _non_empty(cls, v: str, info: ValidationInfo) -> str:
        if not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return v.strip()


class EquipmentHandlerUpdate(_EquipmentUsageHoursValidationMixin, DataEntryUpdate):
    active_usage_hours_per_week: Optional[int] = None
    standby_usage_hours_per_week: Optional[int] = None
    name: Optional[str] = None
    equipment_class: Optional[str] = None
    sub_class: Optional[str] = None
    note: Optional[str] = None
