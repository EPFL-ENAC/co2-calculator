from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Column, Integer
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.models.user import UserProvider

# from app.models.user import UserProvider


# ==========================================
# 0. ENUMERATIONS
# ==========================================
class EntityType(int, Enum):
    """
    Docstring for EntityType

    :var MODULE_PER_YEAR: Description
    :vartype MODULE_PER_YEAR: Literal[2]
    :var MODULE_UNIT_SPECIFIC: Description
    :vartype MODULE_UNIT_SPECIFIC: Literal[3]
    """

    MODULE_PER_YEAR = 2
    MODULE_UNIT_SPECIFIC = 3


class FactorType(int, Enum):
    """
    Docstring for FactorType

    :var EMISSION_FACTOR: Description
    :vartype EMISSION_FACTOR: Literal[0]
    :var MODULE_FACTOR: Description
    :vartype MODULE_FACTOR: Literal[1]
    """

    EMISSION_FACTOR = 0
    MODULE_FACTOR = 1


class IngestionMethod(int, Enum):
    """
    Docstring for IngestionMethod

    :var api: Description
    :vartype api: Literal[0]
    :var csv: Description
    :vartype csv: Literal[1]
    :var manual: Description
    :vartype manual: Literal[2]
    """

    api = 0
    csv = 1
    manual = 2


class TargetType(int, Enum):
    """
    Docstring for TargetType

    :var DATA_ENTRIES: Description
    :vartype DATA_ENTRIES: Literal[0]
    :var FACTORS: Description
    :vartype FACTORS: Literal[1]
    """

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

    _entity_type_comment = (
        "Type of job: module_per_year, module_unit_specific (EnumInt)"
    )
    entity_type: EntityType = Field(
        sa_column=Column(
            SAEnum(EntityType, name="entity_type_enum", native_enum=True),
            nullable=False,
        ),
        description=_entity_type_comment,
    )

    _entity_id_comment = "NULLABLE: FK carbon_report_modules.id if module_unit_specific"
    entity_id: Optional[int] = Field(
        default=None,
        description=_entity_id_comment,
        sa_column=Column(
            Integer,
            nullable=True,
        ),
    )

    # consider changing to ModuleTypeEnum with setter getter conversion
    _module_type_id_comment = "NULLABLE: ModuleTypeEnum the job is for "
    module_type_id: Optional[int] = Field(
        default=None,
        description=_module_type_id_comment,
        sa_column=Column(Integer, nullable=True),
    )

    _data_entry_type_id_comment = "NULLABLE: DataEntryTypeEnum the job is for"
    data_entry_type_id: Optional[int] = Field(
        default=None,
        description=_data_entry_type_id_comment,
        sa_column=Column(Integer, nullable=True),
    )

    _year_comment = "NULLABLE: Year the job is for if applicable"
    year: Optional[int] = Field(
        default=None,
        description=_year_comment,
        sa_column=Column(Integer, nullable=True),
    )

    """ could be Whatever new Enum we create later, like users or units"""
    _target_type_comment = "NULLABLE: Target type: data_entries or factors _ EnumInt"
    target_type: Optional[TargetType] = Field(
        default=None,
        sa_column=Column(
            SAEnum(TargetType, name="target_type_enum", native_enum=True),
            nullable=True,
        ),
        description=_target_type_comment,
    )

    _ingestion_method_comment = "Method used to ingest the data: api, csv, EnumInt"
    ingestion_method: IngestionMethod = Field(
        default=IngestionMethod.api,
        sa_column=Column(
            SAEnum(IngestionMethod, name="ingestion_method_enum", native_enum=True),
            nullable=False,
        ),
        description=_ingestion_method_comment,
    )

    _provider_comment = "Sync source provider _ accred, default, test"
    provider: UserProvider = Field(
        default=UserProvider.DEFAULT.value,
        sa_column=Column(
            SAEnum(UserProvider, name="user_provider_enum", native_enum=True),
            nullable=False,
        ),
        description=_provider_comment,
    )

    _status_comment = "Current status of the ingestion job IngestionStatus"
    status: IngestionStatus = Field(
        default=IngestionStatus.NOT_STARTED,
        sa_column=Column(
            SAEnum(IngestionStatus, name="ingestion_status_enum", native_enum=True),
            nullable=False,
        ),
        description=_status_comment,
    )

    _status_message_comment = "NULLABLE: Detailed status or error message"
    status_message: Optional[str] = Field(
        default=None,
        description=_status_message_comment,
    )

    _meta_comment = "NULLABLE: Additional metadata as json"
    meta: Optional[dict] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description=_meta_comment,
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
