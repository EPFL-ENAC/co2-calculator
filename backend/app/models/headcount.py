from datetime import date as dt_date
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import text
from sqlmodel import Field, SQLModel

# ==========================================
# 1. SHARED MIXINS
# ==========================================


class AuditMixin(SQLModel):
    """
    Reusable mixin for created/updated timestamps.
    Included in Table and Read models, but excluded from Create/Update models.
    """

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")},
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={
            "server_default": text("CURRENT_TIMESTAMP"),
            "onupdate": text("CURRENT_TIMESTAMP"),
        },
        nullable=False,
    )
    # Assuming user IDs are strings (e.g., Keycloak ID or Sciper)
    created_by: Optional[str] = Field(default=None, index=True)
    updated_by: Optional[str] = Field(default=None, index=True)


# ==========================================
# 2. BASE MODEL
# ==========================================


class HeadCountBase(SQLModel):
    """
    Shared fields. These are required when Creating a new record.
    NOTE: 'id', 'provider', and 'audit' fields are excluded here.
    """

    date: dt_date = Field(description="Date of headcount from HR files")

    unit_id: str = Field(
        index=True, max_length=50, description="EPFL unit/department ID"
    )
    unit_name: str = Field(max_length=255, description="Unit name")

    cf: str = Field(max_length=50, description="Cost factor code")
    cf_name: str = Field(max_length=255, description="Cost factor name")
    cf_user_id: str = Field(max_length=50, description="Cost factor user ID")

    display_name: str = Field(max_length=255, description="Display name of the person")
    status: str = Field(
        max_length=100, description="Status (e.g., 'Employé(e) / 13 NSS')"
    )
    function: str = Field(max_length=255, description="Function or role")

    sciper: str = Field(max_length=20, index=True, description="Sciper number")
    ept: float = Field(description="Full-time equivalent percentage (0.0 to 1.0)")


# ==========================================
# 3. TABLE MODEL (Database)
# ==========================================


class HeadCount(HeadCountBase, AuditMixin, table=True):
    """
    The actual Database Table.
    Inherits Base fields + Audit fields + Adds ID and Provider.
    """

    __tablename__ = "headcounts"

    # ID: Integer, Primary Key, Auto-Increment (Serial/Identity)
    id: Optional[int] = Field(default=None, primary_key=True)

    # Provider: Set by system/logic, not by user input directly
    provider: Optional[str] = Field(
        default=None, max_length=50, description="Source: 'api', 'csv', 'manual'"
    )

    def __repr__(self) -> str:
        return f"<HeadCount id={self.id} sciper={self.sciper} date={self.date}>"


# ==========================================
# 4. API INPUT MODELS (DTOs)
# ==========================================


class HeadCountCreate(HeadCountBase):
    """
    Body payload for POST requests.
    Exact copy of Base (all fields required), but no ID/Audit/Provider allowed.
    """

    pass


class HeadCountUpdate(SQLModel):
    """
    Body payload for PATCH requests.
    All fields are Optional. We do NOT inherit from Base to avoid
    required field conflicts.
    """

    date: Optional[dt_date] = None
    unit_id: Optional[str] = None
    unit_name: Optional[str] = None
    cf: Optional[str] = None
    cf_name: Optional[str] = None
    cf_user_id: Optional[str] = None
    display_name: Optional[str] = None
    status: Optional[str] = None
    function: Optional[str] = None
    sciper: Optional[str] = None
    ept: Optional[float] = None
    # We might allow updating the provider manually, or handle it in code
    provider: Optional[str] = None


# ==========================================
# 5. API OUTPUT MODELS (DTOs)
# ==========================================


class HeadCountRead(HeadCountBase, AuditMixin):
    """
    Response schema for GET requests.
    Returns Data + ID + Provider + Audit timestamps.
    """

    id: int
    provider: Optional[str]


class HeadCountList(SQLModel):
    """
    Response schema for Paginated Lists.
    """

    items: List[HeadCountRead]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size
