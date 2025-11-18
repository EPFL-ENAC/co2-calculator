"""Security utilities for JWT authentication and authorization."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from joserfc import jwt
from joserfc.errors import BadSignatureError
from joserfc.jwk import OctKey
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db import get_db
from app.models.user import User
from app.repositories.user_repo import get_user_by_id

settings = get_settings()
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    if expires_delta is None:
        raise ValueError("expires_delta must be provided for access tokens")
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})

    key = OctKey.import_key(settings.SECRET_KEY.encode())
    encoded_jwt = jwt.encode({"alg": settings.ALGORITHM}, to_encode, key)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT refresh token."""
    if expires_delta is None:
        raise ValueError("expires_delta must be provided for access tokens")
    to_encode = data.copy()
    to_encode["type"] = "refresh"  # Mark as refresh token
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})

    key = OctKey.import_key(settings.SECRET_KEY.encode())
    encoded_jwt = jwt.encode({"alg": settings.ALGORITHM}, to_encode, key)
    return encoded_jwt


def decode_jwt(token: str) -> dict:
    """Decode and validate JWT token."""
    try:
        key = OctKey.import_key(settings.SECRET_KEY.encode())
        payload = jwt.decode(token, key, algorithms=[settings.ALGORITHM])
        return payload.claims
    except BadSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency to get current authenticated user.

    Validates JWT token and returns the user object.
    """
    token = credentials.credentials
    payload = decode_jwt(token)

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(db: AsyncSession = Depends(get_db)) -> User:
    """Dependency to ensure user is active."""
    user = await get_current_user(db=db)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return user
