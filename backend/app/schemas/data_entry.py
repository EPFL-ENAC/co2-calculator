from typing import Optional, Protocol, TypeVar

from pydantic import BaseModel

from app.models.data_entry import DataEntryBase
from app.models.data_entry_type import DataEntryTypeEnum

# == =========== DTO BASE ================================= #

T = TypeVar("T", bound=BaseModel)


class Flattener(Protocol[T]):
    dto: type[T]

    def __call__(self, data_entry) -> T: ...


# ============ DTO INPUT ================================= #


class DataEntryCreate(DataEntryBase):
    """Base factor schema."""

    data: dict


class DataEntryUpdate(DataEntryBase):
    """Schema for updating a DataEntry item."""

    data: dict


# ============ DTO OUTPUT ================================= #
class DataEntryResponse(DataEntryBase):
    """Response schema for DataEntry items."""

    id: int
    data_entry_type_id: Optional[int]
    carbon_report_module_id: int
    data: dict


class DataEntryResponseGen(DataEntryBase):
    """Response schema for DataEntry items."""

    id: int
    data_entry_type_id: Optional[int]
    carbon_report_module_id: int


class EquipmentFlattenerResponse(DataEntryResponseGen):
    active_usage_hours: int
    passive_usage_hours: int
    name: str
    power_factor_id: int
    emission: float
    active_power_w: int
    standby_power_w: int


# ----------- Flatteners --------------------------------- #


FLATTENERS: dict[DataEntryTypeEnum, Flattener] = {}


def register_flattener(key: DataEntryTypeEnum):
    def decorator(cls):
        FLATTENERS[key] = cls()
        return cls

    return decorator


@register_flattener(DataEntryTypeEnum.it)
@register_flattener(DataEntryTypeEnum.scientific)
@register_flattener(DataEntryTypeEnum.other)
class EquipmentFlattener:
    dto = EquipmentFlattenerResponse

    def __call__(self, data_entry) -> EquipmentFlattenerResponse:
        return self.dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "active_power_w": data_entry.data["primary_factor"]["active_power_w"],
                "standby_power_w": data_entry.data["primary_factor"]["standby_power_w"],
            }
        )


print(FLATTENERS)
