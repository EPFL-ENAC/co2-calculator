"""Authentication endpoints for OAuth2/OIDC with Entra ID."""

import logging
from datetime import timedelta
from typing import Any, Optional

from authlib.integrations.base_client.errors import MismatchingStateError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
)
from app.models.audit import AuditChangeTypeEnum
from app.models.user import UserProvider
from app.providers.role_provider import RoleProviderNetworkError, get_role_provider
from app.schemas.user import UserRead
from app.services.audit_service import AuditDocumentService
from app.services.user_service import UserService
from app.utils.request_context import extract_ip_address, extract_route_payload

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()

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
        data={**token_data, "type": "access"},
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
        secure=not settings.DEBUG,
    )

    # Set refresh token cookie (long-lived)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        max_age=int(refresh_token_expires.total_seconds()),
        path=settings.OAUTH_COOKIE_PATH,
        secure=not settings.DEBUG,
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
) -> None:
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
        logger.warning(
            "Auth audit log failed",
            extra={"error": str(exc), "change_type": change_type},
        )


@router.get(
    "/login-test",
)
async def login_test(
    request: Request,
    role: str = "co2.user.std",
    db: AsyncSession = Depends(get_db),
):
    """
    Test login endpoint for development.

    Simulates a login by setting auth cookies directly.
    Only enabled in DEBUG mode.
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test login is disabled in production",
        )

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


@router.get("/login")
async def login(request: Request):
    """
    Initiate OAuth2 login flow.

    Redirects to Entra ID for authentication.
    """
    if logger.isEnabledFor(logging.DEBUG):
        x_forwarded_headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower().startswith("x-forwarded-")
        }
        logger.debug(
            "Login requested x-forwarded headers",
            extra={"headers": x_forwarded_headers},
        )
    redirect_uri = request.url_for("auth_callback")
    logger.info("Initiating OAuth2 login", extra={"redirect_uri": str(redirect_uri)})
    return await oauth.co2_oauth_provider.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth2 callback endpoint.

    Handles the callback from Entra ID, exchanges the code for tokens,
    creates or updates the user, sets an httpOnly cookie, and redirects to frontend.
    """
    try:
        # Exchange authorization code for tokens
        token = await oauth.co2_oauth_provider.authorize_access_token(request)
        logger.info("OAuth2 token received", extra={"token_keys": list(token.keys())})
        user_info = token.get("userinfo")

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to retrieve user information from OAuth2 provider",
            )

        # Extract user data from OAuth2 response
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

        # Fetch roles using configured role provider
        role_provider = get_role_provider()
        institutional_id = role_provider.get_user_id(user_info)
        # fetch user and roles?
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
                "email": provider_user.get("email", email),
                "function": provider_user.get("function", None),
                "display_name": provider_user.get("display_name", display_name),
                "has_user_id": bool(institutional_id),
                "roles_count": len(provider_user.get("roles", [])),
            },
        )

        # Get or create user
        user = await UserService(db).upsert_user(
            id=None,
            email=provider_user.get("email", email),
            institutional_id=provider_user.get("code", institutional_id),
            display_name=provider_user.get("display_name", display_name),
            roles=provider_user.get("roles", []),
            function=provider_user.get("function", None),
            provider=role_provider.type,
        )
        await db.commit()

        # Redirect to frontend with httpOnly cookies
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
            institutional_id=user.institutional_id,
            provider=str(role_provider.type.value),
            email=user.email,
        )

        logger.info(
            "User authenticated successfully",
            extra={"user_id": user.id, "redirect_to": "/"},
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
        )
        return response

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
            import traceback

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


@router.get("/me", response_model=UserRead, response_model_exclude_none=True)
async def get_me(
    auth_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current authenticated user information.

    Returns user details including id, email, roles.
    Requires valid auth_token cookie.
    Refreshes roles from provider on each call.
    Resolves user by stable identity (institutional_id, provider) from JWT.
    """
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        # Decode and validate token
        payload = decode_jwt(auth_token)
        sub = payload.get("sub")

        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        # Primary: resolve by stable identity (institutional_id, provider)
        institutional_id = payload.get("institutional_id")
        provider_str = payload.get("provider")

        if institutional_id and provider_str:
            try:
                provider = UserProvider(int(provider_str))
            except ValueError:
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
        else:
            # Fallback for legacy tokens with user_id (temporary migration support)
            user_id = payload.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload",
                )
            logger.warning(
                "Legacy token with user_id detected - logging out user",
                extra={"user_id": user_id},
            )
            # Clear legacy cookies to force clean re-login
            response = Response()
            response.delete_cookie(
                key="auth_token",
                path=settings.OAUTH_COOKIE_PATH or "/",
            )
            response.delete_cookie(
                key="refresh_token",
                path=settings.OAUTH_COOKIE_PATH or "/",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please login again.",
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User email missing",
            )

        # create an issue background to refresh roles periodically? cf #334

        user_read = UserRead.from_orm(user)
        return user_read

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user info", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


@router.post("/refresh")
async def refresh_token(
    request: Request,
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

        # Verify it's actually a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # Primary: resolve by stable identity (institutional_id, provider)
        institutional_id = payload.get("institutional_id")
        provider_str = payload.get("provider")

        if institutional_id and provider_str:
            try:
                provider = UserProvider(int(provider_str))
            except ValueError:
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
        else:
            # Fallback for legacy tokens with user_id (temporary migration support)
            user_id = payload.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload",
                )
            logger.warning(
                "Legacy token with user_id detected - logging out user",
                extra={"user_id": user_id},
            )
            # Clear legacy cookies to force clean re-login
            response.delete_cookie(
                key="auth_token",
                path=settings.OAUTH_COOKIE_PATH or "/",
            )
            response.delete_cookie(
                key="refresh_token",
                path=settings.OAUTH_COOKIE_PATH or "/",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please login again.",
            )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
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


@router.post("/logout")
async def logout(
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
