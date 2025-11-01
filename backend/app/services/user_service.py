"""User service for business logic related to users."""

import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.user import User
from app.repositories import user_repo
from app.schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


async def get_user(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get user by ID."""
    return await user_repo.get_user_by_id(db, user_id)


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get user by email."""
    return await user_repo.get_user_by_email(db, email)


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    """
    Authenticate user with email and password.

    Args:
        db: Database session
        email: User email
        password: Plain text password

    Returns:
        User if authentication successful, None otherwise
    """
    user = await user_repo.get_user_by_email(db, email)
    if not user:
        return None

    if not verify_password(password, str(user.hashed_password)):
        return None

    return user


async def create_user(db: AsyncSession, user_create: UserCreate) -> User:
    """
    Create a new user.

    Args:
        db: Database session
        user_create: User creation data

    Returns:
        Created user

    Raises:
        HTTPException: If email or SCIPER already exists
    """
    # Check if email exists
    existing_user = await user_repo.get_user_by_email(db, user_create.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Check if SCIPER exists (if provided)
    if user_create.sciper:
        existing_user = await user_repo.get_user_by_sciper(db, user_create.sciper)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SCIPER already registered",
            )

    return await user_repo.create_user(db, user_create)


async def update_user(
    db: AsyncSession, user_id: str, user_update: UserUpdate, current_user: User
) -> User:
    """
    Update user information.

    Args:
        db: Database session
        user_id: User ID to update
        user_update: User update data
        current_user: Currently authenticated user

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found or unauthorized
    """
    # Check if user exists
    user = user_repo.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check authorization (users can only update themselves unless superuser)
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    # Prepare updates
    updates = user_update.model_dump(exclude_unset=True)

    # Only superusers can change roles
    if "roles" in updates and not current_user.is_superuser:
        del updates["roles"]

    updated_user = await user_repo.update_user(db, user_id, updates)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return updated_user


async def list_users(
    db: AsyncSession, current_user: User, skip: int = 0, limit: int = 100
) -> List[User]:
    """
    List users with authorization.

    Args:
        db: Database session
        current_user: Currently authenticated user
        skip: Number of records to skip
        limit: Maximum number of records

    Returns:
        List of users

    Note:
        - Superusers can see all users
        - Regular users can only see users in their unit
    """
    filters = {}

    # Non-superusers can only see users in their unit
    if not current_user.is_superuser and current_user.unit_id:
        filters["unit_id"] = current_user.unit_id

    return await user_repo.get_users(db, skip=skip, limit=limit, filters=filters)


async def delete_user(db: AsyncSession, user_id: str, current_user: User) -> bool:
    """
    Delete a user.

    Args:
        db: Database session
        user_id: User ID to delete
        current_user: Currently authenticated user

    Returns:
        True if deleted

    Raises:
        HTTPException: If unauthorized or user not found
    """
    # Only superusers can delete users
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete users",
        )

    success = await user_repo.delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return success
