"""Security utilities for JWT authentication and authorization."""

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatch
from typing import Final

from fastapi import (
    BackgroundTasks,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.security import HTTPBearer
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry
from opentelemetry import trace
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import active_users
from app.core.config import get_settings
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import query_policy
from app.core.session_renewal import RENEWED_COOKIE_STATE_KEY
from app.db import get_db
from app.models.user import User, UserProvider
from app.services.user_service import UserService
from app.tasks.role_sync_tasks import trigger_role_sync_for_user
from app.tasks.session_tasks import audit_session_renewal
from app.utils.request_context import extract_ip_address

settings = get_settings()
security = HTTPBearer()
logger = get_logger(__name__)

# Hoisted out of decode_jwt to avoid re-allocating per request — every
# authenticated call goes through decode_jwt. The registry is stateless
# w.r.t. the token being validated (it carries only the global validation
# config), so a single shared instance is safe across the process.
_CLAIMS_REGISTRY = JWTClaimsRegistry()

# Token-type discriminator used as the `type` JWT claim and as the
# `expected_token_type` argument to resolve_user_by_jwt_payload. A named
# constant (not a string literal at call sites) so bandit B106 doesn't
# false-positive: it scans kwargs whose name contains "token" for
# hardcoded credentials, which this decidedly is not.
TOKEN_TYPE_ACCESS: Final[str] = "access"
SESSION_COOKIE: Final[str] = "auth_token"


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    if expires_delta is None:
        raise ValueError("expires_delta must be provided for access tokens")
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire})

    key = OctKey.import_key(settings.JWT_HMAC_KEY.encode())
    encoded_jwt = jwt.encode({"alg": settings.ALGORITHM}, to_encode, key)
    return encoded_jwt


def _session_end(now: int, auth_time: int) -> int:
    """When a cookie minted now must expire: idle window, capped by login age."""
    idle = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    cap = settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600
    return min(now + idle, auth_time + cap)


def issue_session_cookie(
    response: Response,
    *,
    sub: str,
    email: str,
    institutional_id: str,
    provider: str,
    auth_time: int,
) -> None:
    """Mint the one session cookie (#2943).

    ``auth_time`` (OIDC claim) is the login instant and never moves; every
    renewal copies it, so a session slides on activity but ends at
    ``auth_time + REFRESH_TOKEN_EXPIRE_HOURS`` whatever the user does.
    """
    now = int(time.time())
    ttl = _session_end(now, auth_time) - now
    token = create_access_token(
        data={
            "sub": sub,
            "email": email,
            "institutional_id": institutional_id,
            "provider": provider,
            "type": TOKEN_TYPE_ACCESS,
            "auth_time": auth_time,
        },
        expires_delta=timedelta(seconds=ttl),
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=ttl,
        path=settings.OAUTH_COOKIE_PATH,
        secure=settings.COOKIE_SECURE,
    )


def session_needs_renewal(payload: dict, now: int) -> bool:
    """Past half the idle window, and a new cookie would actually last longer.

    A token without ``auth_time`` predates #2943 and is never renewed: it
    lives out its own ``exp`` and the user logs in once.
    """
    auth_time = payload.get("auth_time")
    if auth_time is None:
        return False
    exp = int(payload["exp"])
    half_idle = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 30
    return exp - now < half_idle and _session_end(now, int(auth_time)) > exp


def decode_jwt(token: str) -> dict:
    """Decode and validate JWT token.

    `jwt.decode` validates signature and algorithm but does NOT validate
    payload claims. The explicit `_CLAIMS_REGISTRY.validate` call below
    is what enforces `exp` (expiry) — without it expired tokens remain
    valid until JWT_HMAC_KEY rotates.

    The 401 detail is intentionally opaque: callers don't need to know
    whether the failure was a bad signature, expired token, invalid
    claim or an algorithm we refuse, and disclosing it leaks oracle-style
    information back to whoever sent the token (CWE-209). Every joserfc
    error lands here (#2943): before, ``alg=none`` on a protected route
    was a 500. The underlying exception is logged at INFO so it remains
    diagnosable server-side.
    """
    try:
        key = OctKey.import_key(settings.JWT_HMAC_KEY.encode())
        payload = jwt.decode(token, key, algorithms=[settings.ALGORITHM])
        _CLAIMS_REGISTRY.validate(payload.claims)
        return payload.claims
    except JoseError as e:
        logger.info(
            "JWT validation failed",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def tag_span_with_user(user: User) -> None:
    """Name who is behind the request on the current server span.

    Chasing one tester's traces by IP is unreliable — NAT, VPN and a router
    rescheduled onto an untrusted address all break it. ``{ span.user.id =
    "41" }`` does not.

    Deliberately our own ``User.id``, never the institutional id: a sciper
    identifies a person across every EPFL system, while this id means nothing
    without our database. Traces leave the namespace for a shared collector,
    so the pseudonymous key is the one that belongs there — worth the extra
    lookup it costs us. A no-op without a tracer configured, which is every
    local run.
    """
    trace.get_current_span().set_attribute("user.id", str(user.id))


async def resolve_user_by_jwt_payload(
    payload: dict,
    db: AsyncSession,
    *,
    expected_token_type: str | None = None,
) -> User:
    """Centralized JWT-payload → User resolution.

    Single trust-boundary check shared by `GET /v1/session`,
    `POST /v1/session`, and `get_current_user`. Validates the stable
    (institutional_id, provider)
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
    tag_span_with_user(user)
    active_users.touch(user.id)
    return user


def _renew_session(
    payload: dict,
    user: User,
    request: Request,
    background_tasks: BackgroundTasks,
) -> None:
    """Re-issue the cookie and record the renewal off-request.

    The ``Set-Cookie`` value is parked on the request state, and
    ``SessionRenewalMiddleware`` appends it to whatever response goes out:
    a route returning its own ``Response`` (304, download, stream) would
    otherwise drop it. Both side effects run after the response is sent,
    each with its own DB session: the audit row because a renewal is a
    session event like a login, the role sync because this is the cadence
    ``POST /session`` used to give it (plan 2539).
    """
    carrier = Response()
    issue_session_cookie(
        carrier,
        sub=str(payload["sub"]),
        email=str(payload["email"]),
        institutional_id=str(payload["institutional_id"]),
        provider=str(payload["provider"]),
        auth_time=int(payload["auth_time"]),
    )
    setattr(request.state, RENEWED_COOKIE_STATE_KEY, carrier.headers["set-cookie"])
    background_tasks.add_task(
        audit_session_renewal,
        user_id=user.id or 0,
        institutional_id=user.institutional_id,
        email=user.email,
        ip_address=extract_ip_address(request),
        route_path=request.url.path,
        renewed_exp=int(payload["exp"]),
    )
    background_tasks.add_task(
        trigger_role_sync_for_user, user_id=user.id or 0, force=False
    )


async def get_optional_user(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    auth_token: str | None = Cookie(None),
) -> User | None:
    """The session behind the cookie, or ``None`` when there is no cookie.

    A cookie that is present but does not validate is still a 401: the
    browser sent a credential and it was refused, which is not the same
    state as "anonymous". Past half the idle window the cookie is renewed
    on this response (#2943), so an active user never sees it expire.

    Returns a *detached* ``User`` and hands the pooled connection back
    before the route body runs. ``get_db`` is a ``yield`` dependency that
    FastAPI releases only after the response is fully sent, and the user
    lookup autobegins a transaction, so without the rollback every request
    pinned one connection from auth to the last byte -- for a stream or an
    S3 upload that is minutes, and on 2026-09-08 that queue filled the
    DBaaS PgBouncer (#2654, #2689). The route's own session is untouched:
    its first query autobegins again and takes a connection only then.
    ``User`` has no relationships, so a detached instance is complete.
    """
    if not auth_token:
        return None
    payload = decode_jwt(auth_token)
    user = await resolve_user_by_jwt_payload(
        payload, db, expected_token_type=TOKEN_TYPE_ACCESS
    )
    db.expunge(user)
    await db.rollback()
    if session_needs_renewal(payload, int(time.time())):
        _renew_session(payload, user, request, background_tasks)
    return user


async def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    """Protected-route dependency: the session user, or 401."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Get the current active user.
    Legacy code: used to check for is_active flag, but now all users are active.
    """
    return user


def _build_permission_input(user: User, path: str, action: str) -> dict:
    """Build OPA input data for permission checks.

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
    return await query_policy("authz/permission/check", input_data)


async def is_permitted(user: User, path: str, action: str = "view") -> bool:
    """Check if the user has the specified permission.
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


async def check_permission(
    user: User,
    path: str,
    action: str = "view",
    detail: str = "You do not have permission to perform this action",
) -> None:
    """Raise 403 unless the user has the permission; supports globs ("modules.*").

    The one log line for a refused request lives here (#2934): every route
    gate goes through it, so a denied backoffice action is greppable by
    user_id and permission path, not just by its 403 access line.
    """
    if not await is_permitted(user, path, action):
        logger.warning(
            "Permission check denied",
            extra={"user_id": sanitize(user.id), "path": path, "action": action},
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_permission(path: str, action: str = "view") -> Callable:
    """Create a FastAPI dependency that checks permissions using OPA pattern.

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
