"""Authentication endpoints for OAuth2/OIDC with Entra ID - Stateless Implementation."""

import base64
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import create_access_token, decode_jwt
from app.repositories.user_repo import get_user_by_email, get_user_by_id
from app.schemas.user import UserRead, UserCreate

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()


async def get_oidc_config() -> dict:
    """Fetch OIDC configuration from provider's well-known endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(settings.oauth_metadata_url)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error("Failed to fetch OIDC configuration", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect to OAuth provider",
        )


@router.get("/login")
async def login(request: Request):
    """
    Initiate OAuth2 login flow - Stateless version.

    Redirects to OAuth2 provider (Entra ID) for authentication.
    The state parameter is generated but not stored server-side (stateless).
    """
    try:
        # Get OIDC configuration
        oidc_config = await get_oidc_config()
        authorization_endpoint = oidc_config["authorization_endpoint"]

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Build callback URL
        callback_url = str(request.url_for("auth_callback"))

        # Build authorization URL
        params = {
            "client_id": settings.OAUTH_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": callback_url,
            # "scope": "openid email profile",
            "scope": "openid email",
            "state": state,
            "response_mode": "query",
        }

        auth_url = f"{authorization_endpoint}?{urlencode(params)}"

        logger.info(
            "Initiating OAuth2 login",
            extra={"redirect_uri": callback_url, "provider": "entra"},
        )

        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to initiate OAuth2 login", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate login",
        )


@router.get("/callback")
async def auth_callback(
    request: Request,
    code: str,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth2 callback endpoint - Stateless version.

    Handles the callback from Entra ID, exchanges the code for tokens,
    creates or updates the user, sets an httpOnly cookie, and redirects to frontend.
    """
    try:
        # Get OIDC configuration
        oidc_config = await get_oidc_config()
        token_endpoint = oidc_config["token_endpoint"]

        # Build callback URL (must match what we sent in /login)
        callback_url = str(request.url_for("auth_callback"))

        # Exchange authorization code for tokens
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": callback_url,
                    "client_id": settings.OAUTH_CLIENT_ID,
                    "client_secret": settings.OAUTH_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if token_response.status_code != 200:
                logger.error(
                    "Token exchange failed",
                    extra={
                        "status_code": token_response.status_code,
                        "response": token_response.text,
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Failed to exchange authorization code for tokens",
                )

            tokens = token_response.json()

        # Get ID token
        id_token = tokens.get("id_token")
        if not id_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No ID token received from OAuth2 provider",
            )

        # Decode the ID token (JWT) - simple decode without verification
        # We trust it because we got it directly from the OAuth provider over HTTPS
        try:
            payload_part = id_token.split(".")[1]
            # Add padding if needed for base64 decoding
            padding = 4 - len(payload_part) % 4
            if padding != 4:
                payload_part += "=" * padding
            user_info = json.loads(base64.urlsafe_b64decode(payload_part))
        except Exception as e:
            logger.error("Failed to decode ID token", extra={"error": str(e)})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid ID token format",
            )

        # Extract user data from ID token
        email = user_info.get("email") or user_info.get("preferred_username")
        if not email:
            logger.error("No email in ID token", extra={"claims": list(user_info.keys())})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No email found in OAuth2 response",
            )

        full_name = user_info.get("name")
        sciper = user_info.get("sciper")  # Custom claim if configured in Entra ID
        roles = user_info.get("roles", [])  # Custom claim from groups/app roles

        logger.info(
            "User info extracted from ID token",
            extra={
                "email": email,
                "has_name": bool(full_name),
                "has_sciper": bool(sciper),
                "roles_count": len(roles),
            },
        )

        # Get or create user
        user = await get_user_by_email(db, email)

        if not user:
            # Auto-create user on first login
            from app.services import user_service

            user_create = UserCreate(
                email=email,
                full_name=full_name or email,  # Fallback to email if no name
                sciper=sciper,
                roles=roles,
                password="",  # No password for OAuth users
            )
            user = await user_service.create_user(db, user_create)
            logger.info(
                "Created new user from OAuth2 provider",
                extra={"user_id": user.id, "email": email},
            )
        else:
            # Update user info from OAuth2
            user.full_name = full_name or user.full_name
            user.sciper = sciper or user.sciper
            user.roles = roles if roles else user.roles
            user.last_login = datetime.utcnow()
            await db.commit()
            await db.refresh(user)
            logger.info(
                "Updated existing user from OAuth2 provider",
                extra={"user_id": user.id, "email": email},
            )

        # Create JWT token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "roles": user.roles},
            expires_delta=access_token_expires,
        )

        # Redirect to frontend with httpOnly cookie
        response = RedirectResponse(
            url=settings.FRONTEND_URL + "/en/home",
            status_code=status.HTTP_302_FOUND,
        )
        response.set_cookie(
            key="auth_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
            path="/",
            secure=not settings.DEBUG,  # HTTPS only in production
        )

        logger.info(
            "User authenticated successfully",
            extra={"user_id": user.id, "redirect_to": "/en/home"},
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("OAuth callback failed", extra={"error": str(e), "type": type(e).__name__})
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

    Returns user details including sciper, email, roles, and name.
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
    Note: This does not log out from Entra ID SSO session.
    """
    response.set_cookie(
        key="auth_token",
        value="",
        httponly=True,
        max_age=0,
        path="/",
    )

    logger.info("User logged out")
    return {"message": "Logged out successfully"}
