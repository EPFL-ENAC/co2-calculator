"""User API endpoints."""

import logging
from datetime import timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserRead, UserUpdate
from app.services import user_service

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth2 compatible token login endpoint.

    Use email as username and password to get a JWT token.
    """
    user = await user_service.authenticate_user(
        db, form_data.username, form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email, "roles": user.roles},
        expires_delta=access_token_expires,
    )

    logger.info(f"User {user.id} logged in successfully")
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user.

    This is a public endpoint (no authentication required).
    """
    logger.info(f"New user registration: {user_create.email}")
    user = await user_service.create_user(db, user_create)
    logger.info(f"User {user.id} registered successfully")
    return user


@router.get("/me", response_model=UserRead)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    """Get current user information."""
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update current user information."""
    updated_user = await user_service.update_user(
        db, str(current_user.id), user_update, current_user
    )
    return updated_user


@router.get("/", response_model=List[UserRead])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List users.

    Regular users can only see users in their unit.
    Superusers can see all users.
    """
    users = await user_service.list_users(db, current_user, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get user by ID."""
    user = await user_service.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Users can only see themselves or users in their unit (unless superuser)
    if (
        user_id != current_user.id
        and not current_user.is_superuser
        and user.unit_id != current_user.unit_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user",
        )

    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update user by ID."""
    updated_user = await user_service.update_user(db, user_id, user_update, current_user)
    return updated_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete user (superuser only)."""
    await user_service.delete_user(db, user_id, current_user)
    return None
