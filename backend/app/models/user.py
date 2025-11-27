"""User model for authentication and authorization."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    """User model representing authenticated users in the system."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)

    # EPFL-specific fields
    sciper: Mapped[Optional[int]] = mapped_column(
        Integer, unique=True, index=True, nullable=True, comment="EPFL SCIPER number"
    )

    # Role-based access control (hierarchical structure)
    # Format: [{"role": "co2.user.std", "on": {"unit": "12345"}}]
    roles: Mapped[List[dict]] = mapped_column(
        JSON, default=list, comment="User roles with hierarchical scopes"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    resources = relationship("Resource", back_populates="owner")

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role (any scope).

        Args:
            role: Role name to check (e.g., "co2.user.std")

        Returns:
            True if user has the role with any scope
        """
        if not self.roles:
            return False
        return any(r.get("role") == role for r in self.roles)

    def has_role_on(self, role: str, scope_type: str, scope_id: str) -> bool:
        """Check if user has a specific role on a specific resource.

        Args:
            role: Role name (e.g., "co2.user.std")
            scope_type: Scope type (e.g., "unit", "affiliation")
            scope_id: Scope identifier (e.g., "12345")

        Returns:
            True if user has the role on the specified resource
        """
        if not self.roles:
            return False
        for r in self.roles:
            if r.get("role") == role:
                on = r.get("on")
                if isinstance(on, dict) and on.get(scope_type) == scope_id:
                    return True
        return False

    def has_role_global(self, role: str) -> bool:
        """Check if user has a specific role with global scope.

        Args:
            role: Role name (e.g., "co2.backoffice.admin")

        Returns:
            True if user has the role with global scope
        """
        if not self.roles:
            return False
        return any(
            r.get("role") == role and r.get("on") == "global" for r in self.roles
        )
