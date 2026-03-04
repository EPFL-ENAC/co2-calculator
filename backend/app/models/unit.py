"""Unit model for CO2 calculation."""

from typing import Optional

from sqlalchemy import Enum as SAEnum
from sqlmodel import Column, Field, SQLModel

from app.models.user import UserProvider

# cost_center --> institutional_id
# principal_user_institutional_id -> principal_user_institutional_id
# provider_code -> institutional_code
# path_cost_center -> path_institutional_id
# path_provider_code -> path_institutional_code
# parent_id -> parent_institutional_code


class UnitBase(SQLModel):
    """Base model for Units representing EPFL units or organizational units."""

    # --- Source ---

    provider: UserProvider = Field(
        default=UserProvider.DEFAULT.value,
        sa_column=Column(
            SAEnum(UserProvider, name="user_provider_enum", native_enum=True),
            nullable=False,
        ),
        description="Domain/source: Sync source provider (accred, default, test)",
    )
    institutional_code: str = Field(
        nullable=False,
        unique=True,
        index=True,
        description="Provider unit.id as string, e.g. '14270'",
    )
    institutional_id: str | None = Field(
        default=None,
        unique=True,
        index=True,
        description="Provider cf, e.g. '7918'. 1:1 with unit, (some units have no cf)",
    )

    # --- Identity ---
    name: str = Field(nullable=False, index=True)
    label_fr: str | None = Field(default=None)
    label_en: str | None = Field(default=None)

    # --- Hierarchy ---
    level: int = Field(nullable=False, index=True)
    parent_institutional_code: str | None = Field(
        default=None,
        # foreign_key="units.institutional_code",
        nullable=True,
        index=True,
        description="Soft reference to parent unit id. No FK constraint "
        "— API data is trusted. Null only for EPFL root (level 1).",
    )
    parent_institutional_id: str | None = Field(
        default=None,
        description="Soft reference to parent unit cf. No FK constraint "
        "— API data is trusted. Null only for EPFL root (level 1).",
    )

    # --- Paths ---
    path_institutional_code: str | None = Field(
        default=None,
        index=True,
        description="Space-sep ids of ancestors, e.g. '10582 10583 11435 14270'. "
        "Primary path for queries: WHERE path_institutional_code LIKE '10000 10201%'",
    )
    path_institutional_id: str | None = Field(
        default=None,
        description="e.g. '8900 8910 7343 7918'. Stored for display, not queried.",
    )
    path_name: str | None = Field(
        default=None,
        description="e.g. 'EHE ASSOCIATIONS SCIENC-CULT 180C'. Human-readable",
    )

    # --- Unit type ---
    unit_type_id: int | None = Field(default=None)
    unit_type_label: str | None = Field(
        default=None,
        description="e.g. 'Laboratoire', 'Plateforme', 'Service central'",
    )

    # --- Principal ---
    principal_user_institutional_id: str | None = Field(
        default=None,
        # foreign_key="users.institutional_id",
        nullable=True,
        index=True,
        description="Soft reference to users.institutional_id (responsible from API)."
        " No FK constraint — API data is trusted.",
    )

    # --- Lifecycle ---
    is_active: bool = Field(default=True, nullable=False)


class Unit(UnitBase, table=True):
    """
    Unit model representing organizational units for CO2 reporting.

    Synced from third-party providers (accred, default, test).

    Units can be filtered based on:
    - id: Internal integer PK
    - institutional_id: Provider-assigned code (e.g., '10208')
    - name: Human-readable name (e.g., 'LCBM')
    """

    __tablename__ = "units"
    id: Optional[int] = Field(default=None, primary_key=True, index=True)

    def __repr__(self) -> str:
        return f"<Unit {self.id} ({self.institutional_id}): {self.name}>"
