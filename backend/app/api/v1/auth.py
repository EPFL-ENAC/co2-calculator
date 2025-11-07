"""Authentication endpoints for OAuth2/OIDC with Entra ID."""

from typing import Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import create_access_token, decode_jwt
from app.repositories.user_repo import get_user_by_email
from app.schemas.user import UserRead

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()

# Configure OAuth with Authlib
oauth = OAuth()
oauth.register(
    name="entra",
    server_metadata_url=settings.oauth_metadata_url,
    client_id=settings.OAUTH_CLIENT_ID,
    client_secret=settings.OAUTH_CLIENT_SECRET,
    client_kwargs={
        "scope": "openid email profile",
    },
)


@router.get("/login")
async def login(request: Request):
    """
    Initiate OAuth2 login flow with your OAuth2 provider.

    Redirects to OAuth2 for authentication, which will redirect back
    to the callback endpoint after successful authentication.
    """
    redirect_uri = request.url_for("auth_callback")
    logger.info("Initiating OAuth2 login", extra={"redirect_uri": str(redirect_uri)})
    return await oauth.entra.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth2 callback endpoint.

    Handles the callback from OAuth2, exchanges the code for tokens,
    creates or updates the user, and sets an auth cookie.
    """
    try:
        # Exchange authorization code for tokens
        token = await oauth.entra.authorize_access_token(request)
        user_info = token.get("userinfo")

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to retrieve user information from OAuth2 provider",
            )

        # Extract user data from OAuth2 response
        email = user_info.get("email") or user_info.get("preferred_username")
        sciper = user_info.get("sciper")  # Custom claim if configured in OAuth2
        full_name = user_info.get("name")
        units = user_info.get("units", [])  # Custom claim
        roles = user_info.get("roles", [])  # Custom claim or from groups

        # Get or create user
        user = await get_user_by_email(db, email)

        if not user:
            # Auto-create user on first login
            from app.schemas.user import UserCreate
            from app.services import user_service

            user_create = UserCreate(
                email=email,
                full_name=full_name,
                sciper=sciper,
                roles=roles,
                password="",  # No password for OAuth users
            )
            user = await user_service.create_oauth_user(db, user_create)
            logger.info(
                "Created new user from OAuth2 provider", extra={"user_id": user.id}
            )

        # Update user info from OAuth2
        user.full_name = full_name
        user.sciper = sciper
        user.roles = roles
        user.last_login = datetime.utcnow()
        await db.commit()

        # Create JWT token
        from datetime import timedelta

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "roles": user.roles},
            expires_delta=access_token_expires,
        )

        # Redirect to frontend with cookie
        response = RedirectResponse(
            url=settings.FRONTEND_URL + "/workspace-setup",
            status_code=status.HTTP_302_FOUND,
        )
        response.set_cookie(
            key="auth_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            max_age=86400,  # 24 hours
            path="/",
            secure=not settings.DEBUG,  # HTTPS only in production
        )

        logger.info(
            "User authenticated via OAuth2 provider", extra={"user_id": user.id}
        )
        return response

    except Exception as e:
        logger.error("OAuth callback failed", extra={"error": str(e)})
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

    Returns user details including sciper, email, roles, units, and name.
    Requires valid auth_token cookie.
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

        # Get user from database
        from app.repositories.user_repo import get_user_by_id

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

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user info", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


@router.post("/logout")
async def logout(response: Response):
    """
    Logout the current user.

    Clears the auth_token cookie and logs out from the application.
    Note: This does not log out from OAuth2 session.
    """
    response.set_cookie(
        key="auth_token",
        value="",
        httponly=True,
        max_age=0,
        path="/",
    )

    return {"message": "Logged out successfully"}
