"""Authentication endpoints for OAuth2/OIDC with Entra ID."""

import logging
from datetime import timedelta
from typing import Optional

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
from app.models.user import UserProvider
from app.providers.role_provider import get_role_provider
from app.schemas.user import UserRead
from app.services.user_service import UserService

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
    user_id: int,
) -> None:
    """
    Helper function to create and set authentication cookies.

    Creates both access and refresh tokens and sets them as httpOnly cookies.
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS)

    token_data = {
        "sub": sub,
        "email": email,
        "user_id": user_id,
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


@router.get(
    "/login-test",
)
async def login_test(
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
        provider_code=code,
        display_name=f"Test User: {sanitized_role}",
        roles=roles,
        provider=UserProvider.TEST,
    )

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
        user_id=user.id,
        email=user.email,
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
        provider_code = role_provider.get_user_id(user_info)
        # fetch user and roles?
        provider_user = await role_provider.get_user_by_user_id(provider_code)

        logger.info(
            "User info retrieved from OAuth2",
            extra={
                "email": provider_user.get("email", email),
                "function": provider_user.get("function", None),
                "display_name": provider_user.get("display_name", display_name),
                "has_user_id": bool(provider_code),
                "roles_count": len(provider_user.get("roles", [])),
            },
        )

        # Get or create user
        user = await UserService(db).upsert_user(
            id=None,
            email=provider_user.get("email", email),
            provider_code=provider_user.get("code", provider_code),
            display_name=provider_user.get("display_name", display_name),
            roles=provider_user.get("roles", []),
            function=provider_user.get("function", None),
            provider=role_provider.type,
        )

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
            user_id=user.id,
            email=user.email,
        )

        logger.info(
            "User authenticated successfully",
            extra={"user_id": user.id, "redirect_to": "/"},
        )
        return response

    except HTTPException:
        logger.error("OAuth callback HTTP exception", exc_info=True)
        raise
    except Exception as e:
        logger.error(
            "OAuth callback failed",
            extra={"error": str(e), "type": type(e).__name__},
            exc_info=settings.DEBUG,
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


@router.get("/me", response_model=UserRead)
async def get_me(
    auth_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current authenticated user information.

    Returns user details including id, email, roles.
    Requires valid auth_token cookie.
    Refreshes roles from provider on each call.
    """
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        # Decode and validate token
        payload = decode_jwt(auth_token)
        user_id = payload.get("user_id")
        sub = payload.get("sub")

        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # Get user from database
        user = await UserService(db).get_by_id(id=user_id)
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
    refresh_token: Optional[str] = Cookie(None),
    response: Response = Response(),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token.

    Client should call this when access token expires.
    Returns new access token in cookie.
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
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        user = await UserService(db).get_by_id(user_id)
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
            user_id=user.id,
            email=user.email,
        )

        logger.info("Token refreshed successfully", extra={"user_id": user.id})
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
async def logout(response: Response):
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
    return {"message": "Logged out successfully"}
