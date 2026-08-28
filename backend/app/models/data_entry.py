"""Generic module model for storing dynamic data across different module types."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, text
from sqlmodel import JSON, Field, SQLModel

from app.models._field_defaults import default_dict, default_utcnow


class DataEntryStatusEnum(int, Enum):
    PENDING = 0
    VALIDATED = 1
    REJECTED = 2


class DataEntryTypeEnum(int, Enum):
    # headcount
    member = 1
    student = 2
    # equipment
    scientific = 10
    it = 11
    other = 12
    # travel
    plane = 20
    train = 21
    # building/room
    building = 30
    energy_combustion = 31
    building_embodied_energy = 32
    # external clouds and ai
    external_clouds = 40
    external_ai = 41
    # process emissions
    process_emissions = 50
    # purchase
    scientific_equipment = 60
    it_equipment = 61
    consumable_accessories = 62
    biological_chemical_gaseous_product = 63
    services = 64
    vehicles = 65
    other_purchases = 66
    purchases_centralized = 67

    # Research facilities: Was internal services
    # Implementation of the module "Research facilities" and its sub-modules:
    research_facilities = 70
    animal_facilities = 71

    # Simulator Plan (planner) kinds — 80+ range. Planner modules whose
    # entry shape differs from the Calculator get their own types here;
    # their handlers live in app/modules_planner.
    planner_headcount = 80
    # Purchases: manual CHF total per submodule XOR one global budget
    # (mutually exclusive — enforced at entry creation).
    planner_purchase = 81
    planner_purchase_budget = 82

    @property
    def is_planner_kind(self) -> bool:
        """Whether this type belongs to the Simulator Plan (80+ range)."""
        return self.value >= 80


class DataEntrySourceEnum(int, Enum):
    """Enum representing the source of a data entry.

    Used to track how data entries were created, enabling selective deletion
    and audit trails for different upload methods.

    #951/#2453: which values bucket into the "user" edit-rights branch is
    hardcoded in TWO places that must move together — there is no shared
    source of truth for this specific bucketing (accepted tradeoff, see
    docs/src/implementation-plans/951-edit-rights-per-dataset-permissions.md):
      - backend: app.core.data_entry_permissions._USER_BRANCH_SOURCES
      - frontend: src/utils/dataEntryPolicy.ts USER_BRANCH_SOURCES
    The line is per-year vs unit-specific, not manual vs uploaded: a
    unit-specific upload is the operator's own data. Adding a new member
    here that should read as "user" means updating both.
    """

    USER_MANUAL = 0  # Manual entry via UI — user-owned, editable
    CSV_MODULE_PER_YEAR = 1  # Backoffice per-year CSV — locked
    CSV_MODULE_UNIT_SPECIFIC = 2  # CSV into one's own module — user-owned, editable
    API_MODULE_PER_YEAR = 3  # Backoffice per-year API sync — locked
    API_MODULE_UNIT_SPECIFIC = 4  # API into one's own module — user-owned, editable
    EXTERNAL_INTEGRATION = 5  # Third-party integration or import — locked
    PLANNER_SNAPSHOT = 6  # Simulator Plan prefill copy of a reference-year entry


# Machine-owned bulk per-year sources. A per-year ingest (CSV upload or API
# sync) is a complete yearly export, so it replaces ALL of these — a CSV
# upload after an API sync (or vice versa) must not collide with the other
# mechanism's rows. Manual entries (USER_MANUAL) and unit-specific uploads
# (*_UNIT_SPECIFIC) are operator-owned and always preserved.
BULK_PER_YEAR_SOURCES: tuple[DataEntrySourceEnum, ...] = (
    DataEntrySourceEnum.CSV_MODULE_PER_YEAR,
    DataEntrySourceEnum.API_MODULE_PER_YEAR,
    DataEntrySourceEnum.EXTERNAL_INTEGRATION,
)


## Will be renamed to data_entries later
class DataEntryBase(SQLModel):
    """Base module model with shared fields."""

    # variant is data_entry_types
    data_entry_type_id: int = Field(
        nullable=False,
        index=True,
        description="Reference to data entry type within module",
    )
    carbon_report_module_id: int = Field(
        foreign_key="carbon_report_modules.id",
        nullable=False,
        index=True,
        description="Reference to parent carbon report module instance",
    )
    data: dict = Field(
        default_factory=default_dict,
        sa_column=Column(JSON),
        description="Dynamic JSON storage for module-specific data",
    )

    status: DataEntryStatusEnum | None = Field(
        default=DataEntryStatusEnum.PENDING,
        description="Optional status field for additional state tracking",
    )

    @property
    def data_entry_type(self) -> DataEntryTypeEnum:
        """Get the data entry type as an enum."""
        return DataEntryTypeEnum(self.data_entry_type_id)

    @data_entry_type.setter
    def data_entry_type(self, value: DataEntryTypeEnum) -> None:
        """Set the data entry type from an enum."""
        self.data_entry_type_id = value.value


# Database model


class DataEntry(DataEntryBase, table=True):
    """Generic module table for storing data across different module types.

    This table provides a flexible storage mechanism where:
    - module_type_id defines the category (headcount, equipment, travel)
    - data_entry_type_id defines the subcategory (student, member, etc.)
    - carbon_report_module_id links to the specific carbon report module instance
    - data stores the actual row data as JSON
    - source tracks the origin (user manual, CSV upload, API, etc.)
    - created_by_id tracks the specific creator (user.id or job.id)

    Examples:
    - Headcount student: module_type=1, data_entry_type=2, data={...}
    - Equipment scientific: module_type=4, data_entry_type=9, data={...}
    """

    __tablename__ = "data_entries"

    __table_args__ = (
        # #2050 J4: one (module, person, role) per member row, enforced by the
        # database. It replaces a check-then-act SELECT in the create workflow
        # that two concurrent POSTs could both pass. A person can legitimately
        # hold several roles in a unit, so sius_code is part of the key (#951).
        # Partial + expression, hence the raw text: the key lives inside the
        # JSON ``data`` column and applies to member rows only.
        Index(
            "uq_member_role_per_module",
            "carbon_report_module_id",
            text("(data ->> 'user_institutional_id')"),
            text("(data ->> 'sius_code')"),
            unique=True,
            postgresql_where=text(
                f"data_entry_type_id = {DataEntryTypeEnum.member.value} "
                f"AND data ->> 'user_institutional_id' IS NOT NULL"
            ),
        ),
    )

    id: int | None = Field(default=None, primary_key=True, index=True)

    # Denormalized scope columns (source of truth is
    # carbon_report_module → carbon_report).  Carried on the row so
    # bulk operations — most importantly the per-year full-replace
    # delete in CSV ingest — can filter by year/unit without resolving
    # the module tree.  Stamped by the bulk ingest paths; immutable
    # facts of an entry (entries never move between modules).
    year: int | None = Field(
        default=None,
        description="Denormalized report year (from carbon_report)",
        sa_column=Column(Integer, nullable=True, index=True),
    )
    unit_id: int | None = Field(
        default=None,
        description="Denormalized unit id (from carbon_report.unit_id)",
        sa_column=Column(Integer, nullable=True, index=True),
    )

    # Source tracking fields
    source: int | None = Field(
        default=None,
        description="Entry source: user manual, CSV upload, API, etc.",
        sa_column=Column(Integer, nullable=True, index=True),
    )
    created_by_id: int | None = Field(
        default=None,
        index=True,
        description="Creator ID: user.id or data_ingestion_job.id",
    )

    created_at: datetime = Field(
        default_factory=default_utcnow,
        sa_column=Column(DateTime, default=datetime.utcnow, nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=default_utcnow,
        sa_column=Column(
            DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DataEntry {self.id}>: "
            f"data_entry_type={self.data_entry_type_id} "
            f"carbon_report_module={self.carbon_report_module_id} "
            f"source={self.source}>"
        )
