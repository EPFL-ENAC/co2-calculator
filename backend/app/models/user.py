"""User model for authentication and authorization."""

from datetime import datetime
from typing import List

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    """User model representing authenticated users in the system."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)

    # EPFL-specific fields
    unit_id = Column(
        String, index=True, nullable=True, comment="EPFL unit/department ID"
    )
    sciper = Column(
        String, unique=True, index=True, nullable=True, comment="EPFL SCIPER number"
    )

    # Role-based access control
    roles: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, comment="User roles for the user"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationships
    resources = relationship("Resource", back_populates="owner")

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in (self.roles or [])

    def has_any_role(self, roles: List[str]) -> bool:
        """Check if user has any of the specified roles."""
        user_roles = set(self.roles or [])
        return bool(user_roles.intersection(roles))
