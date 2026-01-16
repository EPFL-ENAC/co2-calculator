"""Security utilities for JWT authentication and authorization."""

from datetime import datetime, timedelta
from typing import Callable, Optional

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from joserfc import jwt
from joserfc.errors import BadSignatureError
from joserfc.jwk import OctKey
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import query_policy
from app.db import get_db
from app.models.user import RoleName, User
from app.repositories.user_repo import UserRepository

settings = get_settings()
security = HTTPBearer()
logger = get_logger(__name__)


async def get_jwt_from_cookie(auth_token: str = Cookie(None)):
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return auth_token


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
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_jwt_from_cookie),
) -> User:
    payload = decode_jwt(token)

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    # Re-validate to trigger deserialize_roles validator
    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user


def get_current_active_user_with_any_role(roles: list[RoleName]):
    """
    DEPRECATED: Use require_permission() instead for permission-based authorization.

    Require that the user has at least one of the roles to perform an operation.

    This function is deprecated in favor of permission-based authorization using
    require_permission(path, action). It is kept temporarily for backward compatibility.

    Args:
        roles: List of roles, at least one of which the user must have

    Returns:
        FastAPI dependency that returns authenticated user if role check passes

    Example (OLD - deprecated):
        user: User = Depends(
            get_current_active_user_with_any_role([RoleName.CO2_BACKOFFICE_ADMIN])
        )

    Example (NEW - recommended):
        user: User = Depends(require_permission("backoffice.files", "view"))
    """

    async def get_current_active_user_with_any_role_impl(
        user: User = Depends(get_current_active_user),
    ) -> User:
        # Log usage for migration tracking
        logger.warning(
            "DEPRECATED: get_current_active_user_with_any_role() used. "
            "Migrate to require_permission() for permission-based authorization.",
            extra={
                "user_id": sanitize(user.id),
                "required_roles": [role.value for role in roles],
            },
        )

        if not any(
            role in [user_role.role for user_role in user.roles] for role in roles
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorised to perform this operation",
            )
        return user

    return get_current_active_user_with_any_role_impl


def _build_permission_input(user: User, path: str, action: str) -> dict:
    """
    Build OPA input data for permission checks.

    Similar to _build_opa_input() in resource_service.py, but focused on permissions.

    Args:
        user: Current user
        path: Permission path (e.g., "modules.headcount")
        action: Permission action (e.g., "view", "edit", "export")

    Returns:
        OPA input dictionary with user context and permission details
    """
    input_data = {
        "user": {"id": user.id, "email": user.email, "roles": user.roles or []},
        "path": path,
        "action": action,
    }

    return input_data


def require_permission(path: str, action: str = "view") -> Callable:
    """
    Create a FastAPI dependency that checks permissions using OPA pattern.

    This follows the same pattern as resource_service.py:
    1. Build OPA input with user context
    2. Query policy: decision = await query_policy("authz/permission/check", input_data)
    3. Check decision: if not decision.get("allow"): raise HTTPException(403)
    4. Return authenticated user if permission granted

    Args:
        path: Permission path (e.g., "modules.headcount")
        action: Permission action (e.g., "view", "edit", "export", default: "view")

    Returns:
        FastAPI dependency function that returns User if permission granted

    Usage:
        ```python
        @router.get("/headcounts")
        async def list_headcounts(
            user: User = Depends(require_permission("modules.headcount", "view")),
            db: AsyncSession = Depends(get_db),
        ):
            # User has permission, proceed with request
            ...
        ```
    """

    async def require_permission_impl(
        user: User = Depends(get_current_active_user),
    ) -> User:
        # Build OPA input with user context
        input_data = _build_permission_input(user, path, action)

        # Query policy for authorization decision
        decision = await query_policy("authz/permission/check", input_data)
        logger.info(
            "Permission check requested",
            extra={
                "user_id": sanitize(user.id),
                "path": path,
                "action": action,
                "decision": decision,
            },
        )

        # Check decision
        if not decision.get("allow", False):
            reason = decision.get("reason", "Permission denied")
            logger.warning(
                "Permission check denied",
                extra={
                    "user_id": sanitize(user.id),
                    "path": path,
                    "action": action,
                    "reason": reason,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {reason}",
            )

        # Return authenticated user if permission granted
        return user

    return require_permission_impl
