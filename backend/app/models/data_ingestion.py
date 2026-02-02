from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.models.user import UserProvider

# from app.models.user import UserProvider


# ==========================================
# 0. ENUMERATIONS
# ==========================================
class EntityType(int, Enum):
    ALL_USERS = 0
    ALL_UNITS = 1
    MODULE_PER_YEAR = 2
    MODULE_UNIT_SPECIFIC = 3


class FactorType(int, Enum):
    EMISSION_FACTOR = 0
    MODULE_FACTOR = 1


class IngestionMethod(int, Enum):
    api = 0
    csv = 1
    manual = 2


class TargetType(int, Enum):
    DATA_ENTRIES = 0
    FACTORS = 1


class IngestionStatus(int, Enum):
    NOT_STARTED = 0
    PENDING = 1
    IN_PROGRESS = 2
    COMPLETED = 3
    FAILED = 4


# ==========================================
# 1. BASE MODEL
# ==========================================


class DataIngestionJobBase(SQLModel):
    """
    Shared fields. Required when creating a new record.
    """

    entity_type: EntityType = Field(
        sa_column=Column(
            SAEnum(EntityType, name="entity_type_enum", native_enum=True),
            nullable=False,
        ),
        description="Type of entity the job is for",
    )

    entity_id: Optional[int] = Field(
        default=None,
        description="FK to carbon_report_modules.id. for module_unit_specific jobs",
    )

    # consider changing to ModuleTypeEnum with setter getter conversion
    module_type_id: Optional[int] = Field(
        default=None,
        description="For module_per_year/module_unit_specific",
    )

    year: Optional[int] = Field(
        default=None, description="For module_per_year/module_unit_specific"
    )

    target_type: Optional[TargetType] = Field(
        default=None,
        sa_column=Column(
            SAEnum(TargetType, name="target_type_enum", native_enum=True),
            nullable=True,
        ),
        description="0: 'data_entries' or 1: 'factors'",
    )

    ingestion_method: IngestionMethod = Field(
        default=IngestionMethod.api,
        sa_column=Column(
            SAEnum(IngestionMethod, name="ingestion_method_enum", native_enum=True),
            nullable=False,
        ),
        description="Method used to ingest the data",
    )

    provider: UserProvider = Field(
        default=UserProvider.DEFAULT.value,
        sa_column=Column(
            SAEnum(UserProvider, name="user_provider_enum", native_enum=True),
            nullable=False,
        ),
        description="Sync source provider (accred, default, test)",
    )

    status: IngestionStatus = Field(
        default=IngestionStatus.NOT_STARTED,
        sa_column=Column(
            SAEnum(IngestionStatus, name="ingestion_status_enum", native_enum=True),
            nullable=False,
        ),
        description="Current status of the ingestion job",
    )

    status_message: Optional[str] = Field(
        default=None, description="Detailed status or error message"
    )

    meta: Optional[dict] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Additional metadata as JSON",
    )


# ==========================================
# 2. TABLE MODEL (Database)
# ==========================================


class DataIngestionJob(DataIngestionJobBase, table=True):
    __tablename__ = "data_ingestion_jobs"

    id: Optional[int] = Field(default=None, primary_key=True)

    def __repr__(self) -> str:
        return f"""<DataIngestionJob id={self.id}
            provider={self.provider} status={self.status}>"""
