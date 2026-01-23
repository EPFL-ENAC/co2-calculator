from typing import Optional

from app.models.data_entry import DataEntryBase

# from app.models.headcount import HeadCountCreateRequest, HeadCountUpdateRequest
# from app.schemas.equipment import EquipmentCreateRequest

# DataEntryCreateRequest = Union[EquipmentCreateRequest, HeadCountCreateRequest]
# DataEntryUpdateRequest = Union[EquipmentCreateRequest, HeadCountUpdateRequest]


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
