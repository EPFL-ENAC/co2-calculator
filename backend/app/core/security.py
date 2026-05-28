"""Security utilities for JWT authentication and authorization."""

import asyncio
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from typing import Callable, Optional

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from joserfc import jwt
from joserfc.errors import BadSignatureError, ExpiredTokenError, InvalidClaimError
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import query_policy
from app.db import get_db
from app.models.user import User, UserProvider
from app.services.user_service import UserService

settings = get_settings()
security = HTTPBearer()
logger = get_logger(__name__)

# Hoisted out of decode_jwt to avoid re-allocating per request — every
# authenticated call goes through decode_jwt. The registry is stateless
# w.r.t. the token being validated (it carries only the global validation
# config), so a single shared instance is safe across the process.
_CLAIMS_REGISTRY = JWTClaimsRegistry()


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
    expire = datetime.now(timezone.utc) + expires_delta
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
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})

    key = OctKey.import_key(settings.SECRET_KEY.encode())
    encoded_jwt = jwt.encode({"alg": settings.ALGORITHM}, to_encode, key)
    return encoded_jwt


def decode_jwt(token: str) -> dict:
    """Decode and validate JWT token.

    `jwt.decode` validates signature and algorithm but does NOT validate
    payload claims. The explicit `_CLAIMS_REGISTRY.validate` call below
    is what enforces `exp` (expiry) — without it expired tokens remain
    valid until SECRET_KEY rotates.

    The 401 detail is intentionally opaque: callers don't need to know
    whether the failure was a bad signature, expired token, or invalid
    claim, and disclosing it leaks oracle-style information back to
    whoever sent the token (CWE-209). The underlying exception is logged
    at INFO so it remains diagnosable server-side.
    """
    try:
        key = OctKey.import_key(settings.SECRET_KEY.encode())
        payload = jwt.decode(token, key, algorithms=[settings.ALGORITHM])
        _CLAIMS_REGISTRY.validate(payload.claims)
        return payload.claims
    except (BadSignatureError, ExpiredTokenError, InvalidClaimError) as e:
        logger.info(
            "JWT validation failed",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def resolve_user_by_jwt_payload(
    payload: dict,
    db: AsyncSession,
    *,
    expected_token_type: Optional[str] = None,
) -> User:
    """Centralized JWT-payload → User resolution.

    Single trust-boundary check shared by /auth/me, /auth/refresh, and
    `get_current_user`. Validates the stable (institutional_id, provider)
    identity pair, rejects legacy user_id-only tokens, looks the user up,
    and raises 401 on any failure. When ``expected_token_type`` is
    supplied (used by /refresh) the payload's ``type`` field must match.
    """
    if expected_token_type is not None:
        if payload.get("type") != expected_token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

    institutional_id = payload.get("institutional_id")
    provider_str = payload.get("provider")

    if not (institutional_id and provider_str):
        user_id = payload.get("user_id")
        logger.warning(
            "Legacy token without institutional_id/provider detected",
            extra={"user_id": user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Session expired. Please login again."
                if user_id
                else "Invalid token payload"
            ),
        )

    try:
        provider = UserProvider(int(provider_str))
    except ValueError:
        # Guard above already excludes None/empty so TypeError can't fire;
        # int("notanumber") raises ValueError, UserProvider(99999) likewise.
        logger.warning(
            "Invalid provider in token",
            extra={"provider": provider_str},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await UserService(db).get_by_institutional_id_and_provider(
        institutional_id=institutional_id,
        provider=provider,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_jwt_from_cookie),
) -> User:
    """Get current user from JWT token. Thin wrapper over
    :func:`resolve_user_by_jwt_payload` that enforces the access-token
    contract — refresh tokens must not be accepted for protected routes."""
    payload = decode_jwt(token)
    return await resolve_user_by_jwt_payload(payload, db, expected_token_type="access")


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Get the current active user.
    Legacy code: used to check for is_active flag, but now all users are active.
    """
    return user


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


async def get_permission_decision(user: User, path: str, action: str = "view") -> dict:
    """Get OPA decision for a permission check.
    This can be used in cases where you want to get the full decision details instead
    of just the allow/deny result.

    Args:
      user: Current user
      path: Permission path (e.g., "modules.headcount")
      action: Permission action (e.g., "view", "edit", "export", default: "view")

    Returns:
      OPA decision dictionary, e.g. {"allow": True}
        or {"allow": False, "reason": "User does not have required role"}
    """
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
    return decision


async def is_permitted(user: User, path: str, action: str = "view") -> bool:
    """
    Check if the user has the specified permission.
    Supports glob patterns, e.g. path="modules.*" to check all module permissions.

    Args:
        user: Current user
        path: Permission path or glob (e.g., "modules.headcount", "modules.*")
        action: Permission action (e.g., "view", "edit", "export", default: "view")

    Returns:
        True if user has permission for ALL matching paths, False otherwise.
        If the glob matches no known paths, falls through to a direct OPA check.
    """
    known_paths = list(user.calculate_permissions().keys())
    matching_paths = [p for p in known_paths if fnmatch(p, path)]

    if matching_paths:
        results = await asyncio.gather(
            *[get_permission_decision(user, p, action) for p in matching_paths]
        )
        return all(r.get("allow", False) for r in results)

    # No glob match (or literal path) — direct OPA check
    decision = await get_permission_decision(user, path, action)
    return decision.get("allow", False)


async def check_permission(user: User, path: str, action: str = "view") -> None:
    """
    Check if the user has the specified permission and raise HTTPException if not.
    Supports glob patterns, e.g. path="modules.*".

    Args:
        user: Current user
        path: Permission path or glob (e.g., "modules.headcount", "modules.*")
        action: Permission action (e.g., "view", "edit", "export", default: "view")
    Raises:
        HTTPException with status 403 if user does not have permission
        for ANY matching path
    """
    if not await is_permitted(user, path, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )


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
        permitted = await is_permitted(user, path, action)

        if not permitted:
            logger.warning(
                "Permission check denied",
                extra={
                    "user_id": sanitize(user.id),
                    "path": path,
                    "action": action,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )

        return user

    return require_permission_impl
