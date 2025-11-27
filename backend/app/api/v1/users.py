"""User API endpoints.

NOTE: User management endpoints have been removed.
Users are managed internally through OAuth/OIDC authentication only.
User information is available via /auth/me endpoint.

This file is kept for potential future internal user management needs.
"""

from fastapi import APIRouter

router = APIRouter()

# All user management endpoints removed - users are read-only via /auth/me
# Users are auto-created and updated during OAuth login flow
