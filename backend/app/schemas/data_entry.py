from typing import Optional, Union

from app.models.data_entry import DataEntryBase
from app.schemas.equipment import EquipmentCreateRequest
from app.schemas.headcount import HeadCountCreateRequest, HeadCountUpdateRequest

DataEntryCreateRequest = Union[EquipmentCreateRequest, HeadCountCreateRequest]
DataEntryUpdateRequest = Union[EquipmentCreateRequest, HeadCountUpdateRequest]


# ============ DTO INPUT ================================= #


class DataEntryCreate(DataEntryBase):
    """Base factor schema."""

    data: Optional[DataEntryCreateRequest]


class DataEntryUpdate(DataEntryBase):
    """Schema for updating a DataEntry item."""

    data: Optional[DataEntryUpdateRequest]


# ============ DTO OUTPUT ================================= #
class DataEntryResponse(DataEntryBase):
    """Response schema for DataEntry items."""

    id: int
    data_entry_type_id: Optional[int]
    carbon_report_module_id: int
    data: dict
