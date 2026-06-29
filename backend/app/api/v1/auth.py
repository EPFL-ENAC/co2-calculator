"""Authentication endpoints: RESTful session resource + OAuth namespace.

Trust boundaries (see plan
``docs/src/implementation-plans/458-security-authentication-integration-hardening.md``):

1. IdP -> backend: only the ``userinfo`` claims returned by
   ``oauth.co2_oauth_provider.authorize_access_token`` are trusted to bind
   a session to a real identity. Nothing else on the ``/auth/callback``
   request (query params, headers, body) may influence the resolved
   ``institutional_id`` or ``provider``.
2. backend -> cookie: ``/auth/callback`` sets ``auth_token`` /
   ``refresh_token`` cookies directly on the 302 redirect response.
   Frontend and backend share the same domain (``/api`` prefix), so the
   browser accepts ``Set-Cookie`` on the redirect without ITP interference.
   ``_set_auth_cookies`` emits JWTs signed with ``settings.SECRET_KEY``.
3. cookie -> backend: ``decode_jwt`` validates signature, algorithm and
   ``exp``. Any identity in an ``auth_token`` / ``refresh_token`` cookie
   is trusted only after that check passes AND the JWT ``type`` matches
   the endpoint (access for ``GET /v1/session``, refresh for
   ``POST /v1/session``).

The legacy session endpoints (``/v1/auth/me``, ``/v1/auth/refresh``,
``/v1/auth/logout``) were removed and replaced by the RESTful
``/v1/session`` resource (GET / POST / DELETE) — no deprecated aliases.
Per project policy (pre-v1.x, DB drops between deploys) the frontend
lands in lockstep with this change. The IdP-touching routes stayed at
``/v1/auth/{login,callback,login-test}`` to avoid an Entra
``redirect_uri`` reconfiguration; their trust-boundary semantics are
unchanged.

``/v1/auth/login-test`` deliberately bypasses boundary 1 and constructs
a session from a query-string ``role``. Its only gate is
``settings.DEBUG``.
"""

import traceback
from datetime import timedelta
from typing import Any, Optional

from authlib.integrations.base_client.errors import MismatchingStateError
from authlib.integrations.starlette_client import OAuth
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_jwt,
    resolve_user_by_jwt_payload,
)
from app.models.audit import AuditChangeTypeEnum
from app.models.user import UserProvider
from app.providers.role_provider import RoleProviderNetworkError, get_role_provider
from app.schemas.user import UserRead
from app.services.audit_service import AuditDocumentService
from app.services.user_service import UserService
from app.tasks.role_sync_tasks import trigger_role_sync_for_user
from app.utils.request_context import extract_ip_address, extract_route_payload

logger = get_logger(__name__)
settings = get_settings()

# Two routers share this module: ``oauth_router`` hosts the
# browser-driven endpoints (/login, /callback, optional /login-test) and
# ``session_router`` hosts the RESTful session resource (GET/POST/DELETE /session).
oauth_router = APIRouter()
session_router = APIRouter()

# Configure OAuth with Authlib
oauth = OAuth()
oauth.register(
    name="co2_oauth_provider",
    server_metadata_url=settings.oauth_metadata_url,
    client_id=settings.OAUTH_CLIENT_ID,
    client_secret=settings.OAUTH_CLIENT_SECRET,
    client_kwargs={
        "scope": settings.OAUTH_SCOPE,
    },
)


def _set_auth_cookies(
    response: Response,
    sub: str,
    email: str,
    institutional_id: str,
    provider: str,
) -> None:
    """
    Helper function to create and set authentication cookies.

    Creates both access and refresh tokens and sets them as httpOnly cookies.
    Uses stable identity fields (institutional_id, provider) instead of DB primary key.
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS)

    token_data = {
        "sub": sub,
        "email": email,
        "institutional_id": institutional_id,
        "provider": provider,
    }

    access_token = create_access_token(
        data={**token_data, "type": TOKEN_TYPE_ACCESS},
        expires_delta=access_token_expires,
    )

    refresh_token = create_refresh_token(
        data=token_data,
        expires_delta=refresh_token_expires,
    )

    # Set access token cookie (short-lived)
    response.set_cookie(
        key="auth_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=int(access_token_expires.total_seconds()),
        path=settings.OAUTH_COOKIE_PATH,
        secure=settings.COOKIE_SECURE,
    )

    # Set refresh token cookie (long-lived)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        max_age=int(refresh_token_expires.total_seconds()),
        path=settings.OAUTH_COOKIE_PATH,
        secure=settings.COOKIE_SECURE,
    )


def _sanitize_route_payload(payload: Optional[dict]) -> Optional[dict]:
    if not payload:
        return payload

    redacted_keys = {
        "code",
        "state",
        "id_token",
        "access_token",
        "refresh_token",
        "token",
        "authorization",
    }

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: ("[redacted]" if k.lower() in redacted_keys else scrub(v))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    return scrub(payload)


async def _build_request_context(request: Request) -> dict:
    try:
        route_payload = await extract_route_payload(request)
    except Exception:
        route_payload = None

    return {
        "ip_address": extract_ip_address(request),
        "route_path": request.url.path,
        "route_payload": _sanitize_route_payload(route_payload),
    }


async def _log_auth_audit_event(
    *,
    db: AsyncSession,
    request: Request,
    change_type: AuditChangeTypeEnum,
    change_reason: str,
    handler_id: str,
    changed_by: Optional[int],
    data_snapshot: Optional[dict] = None,
    handled_ids: Optional[list[str]] = None,
    entity_id: Optional[int] = None,
    must_succeed: bool = False,
) -> None:
    """Record an auth audit event.

    ``must_succeed=True`` (only the /auth/callback success path) re-raises on
    failure: minting a session without an audit trail is treated as a
    security-contract violation, and the caller's outer handler will
    convert the raise into the standard 401. /session POST and DELETE pass
    ``must_succeed=False`` — the audit failure is logged at ERROR with a
    structured ``audit_failure`` marker for alerting, but the user-facing
    request still succeeds.
    """
    try:
        request_context = await _build_request_context(request)
        audit_service = AuditDocumentService(db)

        await audit_service.create_version(
            entity_type="User",
            entity_id=entity_id if entity_id is not None else 0,
            data_snapshot=data_snapshot or {},
            change_type=change_type,
            changed_by=changed_by,
            change_reason=change_reason,
            handler_id=handler_id,
            handled_ids=handled_ids or [],
            ip_address=request_context.get("ip_address"),
            route_path=request_context.get("route_path"),
            route_payload=request_context.get("route_payload"),
        )
        await db.commit()
    except Exception as exc:
        logger.error(
            "Auth audit log failed",
            extra={
                "error": str(exc),
                "change_type": change_type,
                "audit_failure": True,
            },
        )
        if must_succeed:
            raise


# ---------------------------------------------------------------------------
# /auth/login-test (debug only)
# ---------------------------------------------------------------------------


async def login_test(
    request: Request,
    role: str = "co2.user.std",
    db: AsyncSession = Depends(get_db),
):
    """Test login endpoint for development.

    Registered on the router only when ``settings.DEBUG`` is true (see
    bottom of this module). In a production build the route does not
    exist — clients see 404 rather than 403, and the handler code is
    unreachable.
    """
    # Create a fake user ID and email based on role
    sanitized_role = role.replace("\r\n", "").replace("\n", "")

    # Fetch roles using configured role provider
    role_provider = get_role_provider(UserProvider.TEST)
    user_info = {
        "requested_role": sanitized_role,
        "email": f"testuser_{sanitized_role}@example.org",
        "sub": f"testuser_{sanitized_role}_sub",
    }
    code = role_provider.get_user_id(user_info)
    roles = await role_provider.get_roles(user_info)

    logger.info(
        "Test User info",
        extra={
            "email": user_info.get("email"),
            "has_user_id": bool(code),
            "role": sanitized_role,
        },
    )
    email = user_info.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No email found in test user info",
        )

    # Get or create user
    user = await UserService(db).upsert_user(
        id=None,
        email=email,
        institutional_id=code,
        display_name=f"Test User: {sanitized_role}",
        roles=roles,
        provider=UserProvider.TEST,
    )
    await db.commit()

    # Create response
    response = RedirectResponse(
        url=settings.FRONTEND_URL + "/",
        status_code=status.HTTP_302_FOUND,
    )
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID missing",
        )
    _set_auth_cookies(
        response=response,
        sub=user_info.get("sub", ""),
        institutional_id=user.institutional_id or str(user.id),
        provider=str(UserProvider.TEST.value),
        email=user.email,
    )

    await _log_auth_audit_event(
        db=db,
        request=request,
        change_type=AuditChangeTypeEnum.CREATE,
        change_reason="User login (test)",
        handler_id=user.institutional_id or str(user.id),
        changed_by=user.id,
        handled_ids=[user.institutional_id] if user.institutional_id else [],
        data_snapshot={
            "event": "login_test",
            "user_id": user.id,
            "email": user.email,
            "institutional_id": user.institutional_id,
        },
        entity_id=user.id or 0,
    )

    return response


# ---------------------------------------------------------------------------
# OAuth router: /v1/auth/*
# ---------------------------------------------------------------------------


@oauth_router.get("/login", name="oauth_login")
async def oauth_login(request: Request):
    """
    Initiate OAuth2 login flow.

    Redirects to Entra ID for authentication.
    """
    # ``url_for`` resolves the FastAPI route function name. Keep the name
    # in sync with the @decorator below (``oauth_callback``).
    redirect_uri = request.url_for("oauth_callback")
    # Pods run plain http behind a TLS-terminating LB. COOKIE_SECURE is the
    # deployment's "served over https" flag — force the scheme to match the
    # real public origin. Local http dev keeps COOKIE_SECURE=false so
    # http://localhost is left intact (Entra exempts localhost from https).
    if settings.COOKIE_SECURE and redirect_uri.scheme != "https":
        redirect_uri = redirect_uri.replace(scheme="https")
    logger.info("Initiating OAuth2 login")
    return await oauth.co2_oauth_provider.authorize_redirect(request, redirect_uri)


@oauth_router.get("/callback", name="oauth_callback")
async def oauth_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 callback endpoint.

    Exchanges the OAuth authorization code for ID-token claims, upserts
    the user, audits the event, sets auth cookies on the 302 response,
    and redirects the browser to the app root.

    Frontend and backend share the same domain (``/api`` prefix in
    production), so ``Set-Cookie`` on a redirect response is accepted by
    all browsers without ITP interference.
    """
    try:
        token = await oauth.co2_oauth_provider.authorize_access_token(request)
        logger.info("OAuth2 token received", extra={"token_keys": list(token.keys())})
        user_info = token.get("userinfo")

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to retrieve user information from OAuth2 provider",
            )

        email = user_info.get("email") or user_info.get("preferred_username")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No email found in OAuth2 response",
            )
        display_name = user_info.get("name")
        if user_info.get("given_name") and user_info.get("family_name"):
            display_name = (
                f"{user_info.get('given_name')} {user_info.get('family_name')}"
            )
        if not display_name:
            display_name = email.split("@")[0]

        role_provider = get_role_provider()
        institutional_id = role_provider.get_user_id(user_info)
        try:
            provider_user = await role_provider.get_user_by_user_id(institutional_id)
        except RoleProviderNetworkError as e:
            logger.error(
                "Cannot authenticate: external service unavailable",
                extra={"error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable. Please check your VPN.",
            )

        logger.info(
            "User info retrieved from OAuth2",
            extra={
                "has_user_id": bool(institutional_id),
                "roles_count": len(provider_user.get("roles", [])),
            },
        )

        user = await UserService(db).upsert_user(
            id=None,
            email=provider_user.get("email", email),
            institutional_id=institutional_id,
            display_name=provider_user.get("display_name", display_name),
            roles=provider_user.get("roles", []),
            function=provider_user.get("function", None),
            provider=role_provider.type,
        )
        await db.commit()

        if user.id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID missing",
            )

        await _log_auth_audit_event(
            db=db,
            request=request,
            change_type=AuditChangeTypeEnum.CREATE,
            change_reason="User login",
            handler_id=user.institutional_id or str(user.id),
            changed_by=user.id,
            handled_ids=[user.institutional_id] if user.institutional_id else [],
            data_snapshot={
                "event": "login",
                "user_id": user.id,
                "email": user.email,
                "institutional_id": user.institutional_id,
            },
            entity_id=user.id or 0,
            must_succeed=True,
        )

        redirect = RedirectResponse(
            url=settings.FRONTEND_URL + "/",
            status_code=status.HTTP_302_FOUND,
        )
        _set_auth_cookies(
            response=redirect,
            sub=user_info.get("sub", str(user.id)),
            email=user.email,
            institutional_id=user.institutional_id or str(user.id),
            provider=str(user.provider.value),
        )
        logger.info("Login successful, redirecting to app", extra={"user_id": user.id})
        return redirect

    except MismatchingStateError:
        logger.warning(
            "OAuth state mismatch - session loss or multiple tabs",
        )
        await _log_auth_audit_event(
            db=db,
            request=request,
            change_type=AuditChangeTypeEnum.CREATE,
            change_reason="Login failed: OAuth state mismatch",
            handler_id="unknown",
            changed_by=None,
            data_snapshot={"event": "login_failed", "reason": "state_mismatch"},
            entity_id=0,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication session expired. Please start the login flow again.",
        )
    except HTTPException:
        logger.error("OAuth callback HTTP exception", exc_info=True)
        await _log_auth_audit_event(
            db=db,
            request=request,
            change_type=AuditChangeTypeEnum.CREATE,
            change_reason="Login failed: HTTPException",
            handler_id="unknown",
            changed_by=None,
            data_snapshot={"event": "login_failed", "reason": "http_exception"},
            entity_id=0,
        )
        raise
    except Exception as e:
        logger.error(
            "OAuth callback failed",
            extra={"error": str(e), "type": type(e).__name__},
            exc_info=settings.DEBUG,
        )
        await _log_auth_audit_event(
            db=db,
            request=request,
            change_type=AuditChangeTypeEnum.CREATE,
            change_reason="Login failed: unexpected error",
            handler_id="unknown",
            changed_by=None,
            data_snapshot={
                "event": "login_failed",
                "reason": type(e).__name__,
            },
            entity_id=0,
        )
        if settings.DEBUG:
            tb_lines = traceback.format_exc().splitlines()
            # Return stack trace in response (for dev only)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": str(e), "traceback": tb_lines},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
            )


# /login-test is registered only in DEBUG builds — see the function's
# docstring for the security rationale. In production the route does not
# exist at all.
if settings.DEBUG:
    oauth_router.add_api_route("/login-test", login_test, methods=["GET"])


# ---------------------------------------------------------------------------
# Session router: /v1/session/*
# ---------------------------------------------------------------------------


@session_router.get("", response_model=UserRead, response_model_exclude_none=True)
async def get_session(
    auth_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the current session's user (whoami).

    Requires a valid ``auth_token`` cookie. Resolves user by stable
    identity (institutional_id, provider) from JWT. Uses cached DB
    roles — does not sync from the role provider synchronously.
    """
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_jwt(auth_token)
        user = await resolve_user_by_jwt_payload(
            payload, db, expected_token_type=TOKEN_TYPE_ACCESS
        )

        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User email missing",
            )

        return UserRead.model_validate(user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user info", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


@session_router.post("")
async def refresh_session(
    request: Request,
    background_tasks: BackgroundTasks,
    refresh_token: Optional[str] = Cookie(None),
    response: Response = Response(),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token.

    Client should call this when access token expires.
    Returns new access token in cookie.
    Resolves user by stable identity (institutional_id, provider) from JWT.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    try:
        payload = decode_jwt(refresh_token)
        user = await resolve_user_by_jwt_payload(
            payload, db, expected_token_type=TOKEN_TYPE_REFRESH
        )
        sub = payload.get("sub")
        if not sub:
            # Every JWT we issue carries `sub`; missing it means the token
            # was hand-crafted (signature would already have failed) or the
            # issuance pipeline regressed. Refuse rather than silently
            # passing an empty `sub` into the freshly minted cookies.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User email missing",
            )
        if user.id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID missing",
            )

        # Trigger background role sync if needed (non-blocking)
        # Note: This is fire-and-forget - errors don't affect /session POST response
        if user.id is not None:
            background_tasks.add_task(
                trigger_role_sync_for_user,
                user_id=user.id,
                force=False,
            )

        # Set new tokens
        _set_auth_cookies(
            response=response,
            sub=sub,
            institutional_id=user.institutional_id or str(user.id),
            provider=str(user.provider.value),
            email=user.email,
        )

        logger.info("Token refreshed successfully", extra={"user_id": user.id})

        if request is not None:
            await _log_auth_audit_event(
                db=db,
                request=request,
                change_type=AuditChangeTypeEnum.UPDATE,
                change_reason="Token refreshed",
                handler_id=user.institutional_id or str(user.id),
                changed_by=user.id,
                handled_ids=[user.institutional_id] if user.institutional_id else [],
                data_snapshot={
                    "event": "refresh",
                    "user_id": user.id,
                    "email": user.email,
                    "institutional_id": user.institutional_id,
                },
                entity_id=user.id or 0,
            )
        return {"message": "Token refreshed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Token refresh failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )


@session_router.delete("")
async def delete_session(
    response: Response,
    request: Request,
    auth_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout the current user.

    Clears both auth_token and refresh_token cookies.
    Note: This does not log out from Entra ID SSO session.
    """
    # Clear access token
    response.set_cookie(
        key="auth_token",
        value="",
        httponly=True,
        max_age=0,
        path="/",
    )

    # Clear refresh token
    response.set_cookie(
        key="refresh_token",
        value="",
        httponly=True,
        max_age=0,
        path="/",
    )

    logger.info("User logged out")

    if auth_token:
        try:
            payload = decode_jwt(auth_token)

            # Support both new and legacy token formats for logout audit logging
            institutional_id = payload.get("institutional_id")
            provider_str = payload.get("provider")
            user_id_from_token = payload.get("user_id")  # Legacy

            handler_id = "unknown"
            user_email = payload.get("email")
            user_id = None

            if institutional_id and provider_str:
                # New token format - resolve by stable identity
                try:
                    provider = UserProvider(int(provider_str))
                    user = await UserService(db).get_by_institutional_id_and_provider(
                        institutional_id=institutional_id,
                        provider=provider,
                    )
                    if user:
                        handler_id = user.institutional_id or str(user.id)
                        user_id = user.id
                        user_email = user.email
                except ValueError:
                    logger.warning(
                        "Invalid provider in logout token",
                        extra={"provider": provider_str},
                    )
            elif user_id_from_token:
                # Legacy token format - resolve by user_id
                user = await UserService(db).get_by_id(user_id_from_token)
                if user and user.institutional_id:
                    handler_id = user.institutional_id
                    user_id = user_id_from_token

            await _log_auth_audit_event(
                db=db,
                request=request,
                change_type=AuditChangeTypeEnum.DELETE,
                change_reason="User logout",
                handler_id=handler_id,
                changed_by=user_id,
                handled_ids=[handler_id] if handler_id != "unknown" else [],
                data_snapshot={
                    "event": "logout",
                    "user_id": user_id,
                    "email": user_email,
                },
                entity_id=user_id or 0,
            )
        except Exception as exc:
            logger.warning("Failed to log logout audit", extra={"error": str(exc)})
    return {"message": "Logged out successfully"}
