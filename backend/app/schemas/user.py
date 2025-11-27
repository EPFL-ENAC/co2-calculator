"""User schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    """Schema for reading user data (OAuth-only users).

    Matches the /auth/me response format with hierarchical roles.
    """

    id: str
    sciper: Optional[int] = None
    email: EmailStr
    roles: List[Dict[str, Any]] = []
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True
