"""User schemas for API request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import EmailStr

from app.models import UserBase
from app.models.user import Role


class UserRead(UserBase):
    """Schema for reading user data (OAuth-only users).

    Matches the /auth/me response format with hierarchical roles.
    """

    id: str
    sciper: Optional[str] = None
    email: EmailStr
    roles: List[Role] = []
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
