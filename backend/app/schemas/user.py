"""User schemas for API request/response validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    full_name: Optional[str] = None
    unit_id: Optional[str] = None
    sciper: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(..., min_length=8)
    roles: List[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    unit_id: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    """Schema for reading user data."""

    id: str
    roles: List[str]
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserInDB(UserRead):
    """Schema for user data including sensitive fields."""

    hashed_password: str


class Token(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for JWT token payload data."""

    sub: str
    email: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
