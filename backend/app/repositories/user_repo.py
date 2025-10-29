"""User repository for database operations."""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.crypto import get_password_hash  # Import from crypto module instead
from app.models.user import User
from app.schemas.user import UserCreate


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_sciper(db: Session, sciper: str) -> Optional[User]:
    """Get user by SCIPER number."""
    return db.query(User).filter(User.sciper == sciper).first()


def get_users(
    db: Session, skip: int = 0, limit: int = 100, filters: Optional[dict] = None
) -> List[User]:
    """
    Get list of users with optional filters.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        filters: Dictionary of filters to apply

    Returns:
        List of users
    """
    query = db.query(User)

    if filters:
        for key, value in filters.items():
            if hasattr(User, key):
                query = query.filter(getattr(User, key) == value)

    return query.offset(skip).limit(limit).all()


def get_users_by_unit(db: Session, unit_id: str) -> List[User]:
    """Get all users in a specific unit."""
    return db.query(User).filter(User.unit_id == unit_id).all()


def create_user(db: Session, user: UserCreate) -> User:
    """
    Create a new user.

    Args:
        db: Database session
        user: User creation schema

    Returns:
        Created user
    """
    hashed_password = get_password_hash(user.password)

    db_user = User(
        id=user.email,  # Using email as ID for simplicity
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        unit_id=user.unit_id,
        sciper=user.sciper,
        roles=user.roles or [],
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


def update_user(db: Session, user_id: str, updates: dict) -> Optional[User]:
    """
    Update user fields.

    Args:
        db: Database session
        user_id: User ID
        updates: Dictionary of fields to update

    Returns:
        Updated user or None if not found
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    for key, value in updates.items():
        if value is not None and hasattr(user, key):
            if key == "password":
                setattr(user, "hashed_password", get_password_hash(value))
            else:
                setattr(user, key, value)

    db.commit()
    db.refresh(user)

    return user


def delete_user(db: Session, user_id: str) -> bool:
    """
    Delete a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        True if deleted, False if not found
    """
    user = get_user_by_id(db, user_id)
    if not user:
        return False

    db.delete(user)
    db.commit()

    return True


def count_users(db: Session, filters: Optional[dict] = None) -> int:
    """Count users with optional filters."""
    query = db.query(User)

    if filters:
        for key, value in filters.items():
            if hasattr(User, key):
                query = query.filter(getattr(User, key) == value)

    return query.count()
