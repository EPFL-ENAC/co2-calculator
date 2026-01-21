from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from app.models.user import RoleName


class UnitUser(SQLModel, table=True):
    """Association model linking Users to Units (many-to-many relationship)."""

    __tablename__ = "unit_users"
    unit_id: int = Field(
        default=None,
        nullable=False,
        foreign_key="units.id",
        primary_key=True,
    )
    user_id: int = Field(
        default=None,
        nullable=False,
        foreign_key="users.id",
        primary_key=True,
    )
    role: RoleName = Field(
        default=RoleName.CO2_USER_STD.value,
        sa_column=Column(
            SAEnum(RoleName, name="role_name_enum", native_enum=True),
            nullable=False,
            index=True,
        ),
        description="User's role within the unit",
    )
