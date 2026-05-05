from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, Column, Index, Integer, String, text
from sqlalchemy import UUID as SAUUID
from sqlalchemy import DateTime as SADateTime
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

    Enum integer values are part of the persisted ABI: jobs serialise
    ``entity_type.value`` into ``DataIngestionJob.meta["config"]`` and
    we round-trip via ``EntityType(value)``.  Existing rows have
    ``MODULE_PER_YEAR=1`` and ``MODULE_UNIT_SPECIFIC=2`` baked in, so
    new members MUST be appended (don't insert at the front and shift
    the existing ones — every historical row would silently deserialise
    to the wrong member).

    :var MODULE_PER_YEAR: Description
    :vartype MODULE_PER_YEAR: Literal[1]
    :var MODULE_UNIT_SPECIFIC: Description
    :vartype MODULE_UNIT_SPECIFIC: Literal[2]
    :var GLOBAL_PER_YEAR: Job not scoped to a module
        (e.g. unit sync, role sync).
    :vartype GLOBAL_PER_YEAR: Literal[3]
    """

    MODULE_PER_YEAR = 1
    MODULE_UNIT_SPECIFIC = 2
    GLOBAL_PER_YEAR = 3


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
    :var computed: Recompute factor values from existing emission data
    :vartype computed: Literal[3]
    """

    api = 0
    csv = 1
    manual = 2
    computed = 3


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
    REDUCTION_OBJECTIVES = 2
    REFERENCE_DATA = 3


class IngestionState(int, Enum):
    """Lifecycle state of an ingestion job."""

    NOT_STARTED = 0
    QUEUED = 1
    RUNNING = 2
    FINISHED = 3  # terminal state no more updates expected (error + success)


class IngestionResult(int, Enum):
    """Outcome result of an ingestion job (only valid when state is FINISHED)."""

    SUCCESS = 0
    WARNING = 1
    ERROR = 2


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

    _state_comment = "Lifecycle state of the ingestion job (IngestionState)"
    state: Optional[IngestionState] = Field(
        default=None,
        sa_column=Column(
            SAEnum(IngestionState, name="ingestion_state_enum", native_enum=True),
            nullable=True,
        ),
        description=_state_comment,
    )

    _result_comment = (
        "NULLABLE: Outcome result of the ingestion job"
        " (only valid when state is FINISHED)"
    )
    result: Optional[IngestionResult] = Field(
        default=None,
        sa_column=Column(
            SAEnum(IngestionResult, name="ingestion_result_enum", native_enum=True),
            nullable=True,
        ),
        description=_result_comment,
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
    is_current: bool = Field(
        default=False,
        description=(
            "Whether this is the current active job "
            "for this module/data_entry_type/ingestion_method/target/year combination"
        ),
    )

    # Claiming (Plan 310A)
    locked_by: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255)),
        description="Pod ID that atomically claimed this job",
    )
    locked_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(SADateTime(timezone=True)),
        description="Timestamp of the most recent successful claim",
    )

    # Observability (Plan 310C)
    started_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(SADateTime(timezone=True)),
        description=(
            "Timestamp of the FIRST successful claim — stays put across retries "
            "(unlike locked_at, which updates every claim).  Combined with "
            "finished_at gives true total wall-clock duration."
        ),
    )
    finished_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(SADateTime(timezone=True)),
        description="Timestamp the job reached state=FINISHED",
    )

    # Retry scaffolding (Plan 310A)
    attempts: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
        description="Number of times this job has been attempted",
    )
    max_attempts: int = Field(
        default=3,
        sa_column=Column(Integer, nullable=False, server_default="3"),
        description="Maximum number of attempts before giving up",
    )
    run_after: Optional[datetime] = Field(
        default=None,
        sa_column=Column(SADateTime(timezone=True)),
        description="Earliest time the job may be claimed (NULL = immediately)",
    )

    # Grouping / dispatch (Plan 310A)
    pipeline_id: Optional[UUID] = Field(
        default=None,
        sa_column=Column(SAUUID),
        description="UUID grouping jobs belonging to the same multi-step pipeline run",
    )
    job_type: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100)),
        description="Job type identifier (csv_ingest, factor_ingest, etc.)",
    )

    __table_args__ = (
        Index(
            "ix_data_ingestion_jobs_is_current_unique",
            "module_type_id",
            "data_entry_type_id",
            "target_type",
            "ingestion_method",
            "year",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
        Index(
            "ix_data_ingestion_jobs_pending",
            "run_after",
            postgresql_where=text(
                "state = 'NOT_STARTED'::ingestion_state_enum AND locked_by IS NULL"
            ),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DataIngestionJob id={self.id} "
            f"provider={self.provider} status={self.state} "
            f"result={self.result} is_current={self.is_current}>"
        )
