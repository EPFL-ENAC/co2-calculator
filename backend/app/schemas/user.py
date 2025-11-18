"""User schemas for API request/response validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    """Schema for reading user data (OAuth-only users).
    
    Matches the /auth/me response format with hierarchical roles.
    """

    id: str
    sciper: Optional[str] = None
    email: EmailStr
    roles: List[Dict[str, Any]] = []
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for JWT token payload data."""

    sub: str
    email: Optional[str] = None
    sciper: Optional[str] = None

