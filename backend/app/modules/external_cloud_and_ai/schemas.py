from typing import Optional

from pydantic import field_validator

from app.core.logging import get_logger
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)

logger = get_logger(__name__)


class ExternalCloudHandlerResponse(DataEntryResponseGen):
    service_type: Optional[str] = None
    cloud_provider: Optional[str] = None
    spending: Optional[float] = None
    kg_co2eq: Optional[float] = None


class ExternalAIHandlerResponse(DataEntryResponseGen):
    # ai_provider,ai_use,frequency_use_per_day,user_count
    ai_provider: Optional[str] = None
    ai_use: Optional[str] = None
    frequency_use_per_day: Optional[int] = None
    user_count: Optional[int] = None
    kg_co2eq: Optional[float] = None


class ExternalCloudHandlerCreate(DataEntryCreate):
    service_type: str
    cloud_provider: Optional[str] = None
    spending: float

    @field_validator("spending", mode="after")
    @classmethod
    def validate_spending(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Spending must be non-negative")
        return v


class ExternalAIHandlerCreate(DataEntryCreate):
    ai_provider: str
    ai_use: str
    frequency_use_per_day: Optional[int] = None
    user_count: int

    @field_validator("frequency_use_per_day", "user_count", mode="after")
    @classmethod
    def validate_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


class ExternalCloudHandlerUpdate(DataEntryUpdate):
    service_type: Optional[str] = None
    cloud_provider: Optional[str] = None
    spending: Optional[float] = None

    @field_validator("spending", mode="after")
    @classmethod
    def validate_spending(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Spending must be non-negative")
        return v


class ExternalAIHandlerUpdate(DataEntryUpdate):
    ai_provider: Optional[str] = None
    ai_use: Optional[str] = None
    frequency_use_per_day: Optional[int] = None
    user_count: Optional[int] = None

    @field_validator("frequency_use_per_day", "user_count", mode="after")
    @classmethod
    def validate_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


class ExternalCloudModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_clouds
    create_dto = ExternalCloudHandlerCreate
    update_dto = ExternalCloudHandlerUpdate
    response_dto = ExternalCloudHandlerResponse

    kind_field: str = "cloud_provider"
    subkind_field: str = "service_type"

    sort_map = {
        "id": DataEntry.id,
        "service_type": Factor.classification["subkind"].as_string(),
        "cloud_provider": Factor.classification["kind"].as_string(),
        "spending": DataEntry.data["spending"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "service_type": Factor.classification["subkind"].as_string(),
        "cloud_provider": Factor.classification["kind"].as_string(),
    }

    def to_response(self, data_entry: DataEntry) -> ExternalCloudHandlerResponse:
        primary_factor = data_entry.data.get("primary_factor", {})
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "service_type": primary_factor.get("subkind")
                or data_entry.data.get("service_type"),
                "cloud_provider": primary_factor.get("kind")
                or data_entry.data.get("cloud_provider"),
            }
        )

    def validate_create(self, payload: dict) -> ExternalCloudHandlerCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> ExternalCloudHandlerUpdate:
        return self.update_dto.model_validate(payload)


class ExternalAIModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.external_cloud_and_ai
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.external_ai
    create_dto = ExternalAIHandlerCreate
    update_dto = ExternalAIHandlerUpdate
    response_dto = ExternalAIHandlerResponse

    kind_field: str = "ai_provider"
    subkind_field: str = "ai_use"
    sort_map = {
        "id": DataEntry.id,
        "ai_provider": Factor.classification["kind"].as_string(),
        "ai_use": Factor.classification["subkind"].as_string(),
        "frequency_use_per_day": DataEntry.data["frequency_use_per_day"].as_float(),
        "user_count": DataEntry.data["user_count"].as_float(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
    }

    filter_map = {
        "ai_provider": Factor.classification["kind"].as_string(),
        "ai_use": Factor.classification["subkind"].as_string(),
    }

    def to_response(self, data_entry: DataEntry) -> ExternalAIHandlerResponse:
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data_entry.data,
                "ai_provider": data_entry.data["primary_factor"].get("kind")
                or data_entry.data.get("ai_provider"),
                "ai_use": data_entry.data["primary_factor"].get("subkind")
                or data_entry.data.get("ai_use"),
            }
        )

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(payload)
