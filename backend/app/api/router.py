"""API router configuration."""

from fastapi import APIRouter

from app.api.v1 import resources, users

api_router = APIRouter()

# Include routers
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(resources.router, prefix="/resources", tags=["resources"])
