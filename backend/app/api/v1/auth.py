"""Authentication endpoints for OAuth2/OIDC with Entra ID."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.role_provider import get_role_provider
from app.core.security import create_access_token, create_refresh_token, decode_jwt
from app.repositories.user_repo import get_user_by_id, upsert_user
from app.schemas.user import UserRead

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
    user_id: str,
    email: str,
    sciper: Optional[int] = None,
) -> None:
    """
    Helper function to create and set authentication cookies.

    Creates both access and refresh tokens and sets them as httpOnly cookies.
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS)

    token_data = {
        "sub": user_id,
        "email": email,
        "sciper": sciper,
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
def login_test(role: str = "co2.user.std"):
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
    sanitized_role = role.replace('\r\n', '').replace('\n', '')
    user_id = f"testuser_{sanitized_role}"
    email = "testuser@example.com"
    sciper = 999999

    logger.info(
        "Test User info",
        extra={
            "email": email,
            "has_sciper": bool(sciper),
            "role": sanitized_role,
        },
    )

    # Create response
    response = RedirectResponse(
        url=settings.FRONTEND_URL + "/",
        status_code=status.HTTP_302_FOUND,
    )

    _set_auth_cookies(
        response=response,
        user_id=user_id,
        email=email,
        sciper=sciper,
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

        sciper = int(user_info.get("uniqueid"))  # return sciper as int
        if not sciper:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No SCIPER found in OAuth2 response",
            )
        # Fetch roles using configured role provider
        role_provider = get_role_provider()
        roles = await role_provider.get_roles(user_info, sciper)

        logger.info(
            "User info retrieved from OAuth2",
            extra={
                "email": email,
                "has_sciper": bool(sciper),
                "roles_count": len(roles),
            },
        )

        # Get or create user
        user = await upsert_user(
            db=db,
            email=email,
            sciper=sciper,
            roles=roles,
        )

        # Redirect to frontend with httpOnly cookies
        response = RedirectResponse(
            url=settings.FRONTEND_URL + "/",
            status_code=status.HTTP_302_FOUND,
        )

        _set_auth_cookies(
            response=response,
            user_id=user.id,
            email=user.email,
            sciper=user.sciper,
        )

        logger.info(
            "User authenticated successfully",
            extra={"user_id": user.id, "redirect_to": "/"},
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "OAuth callback failed", extra={"error": str(e), "type": type(e).__name__}
        )
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

    Returns user details including sciper, email, roles.
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
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        # Check it is a test user in DEBUG mode
        if settings.DEBUG and user_id.startswith("testuser_"):
            role = user_id[len("testuser_") :]
            roles = []
            if role == "co2.backoffice.admin":
                roles = [{"role": role, "on": "global"}]
            elif role == "co2.backoffice.std":
                roles = [{"role": role, "on": {"affiliation": "testaffiliation"}}]
            else:
                roles = [{"role": "co2.user.std", "on": {"unit": "testunit"}}]

            # Create a fake user object
            test_user = UserRead(
                id="testuser",
                email="testuser@example.com",
                sciper=999999,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                last_login=datetime.utcnow(),
                roles=roles,
            )
            return test_user

        # Get user from database
        user = await get_user_by_id(db, user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User email missing",
            )
        if not user.sciper:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User sciper missing",
            )

        # Refresh roles from provider
        role_provider = get_role_provider()
        userinfo = {"email": user.email}  # Minimal userinfo for role provider
        fresh_roles = await role_provider.get_roles(userinfo, user.sciper)

        # Update user roles if changed
        if fresh_roles != user.roles:
            user.roles = fresh_roles
            await db.commit()
            await db.refresh(user)
            logger.info(
                "Refreshed user roles",
                extra={"user_id": user.id, "roles_count": len(fresh_roles)},
            )

        return user

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

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # Verify user still exists and is active
        user = await get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        if not user.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User email missing",
            )
        if not user.sciper:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User sciper missing",
            )
        # Set new tokens
        _set_auth_cookies(
            response=response,
            user_id=str(user.id),
            email=str(user.email),
            sciper=user.sciper,
        )

        logger.info("Token refreshed successfully", extra={"user_id": user_id})
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
