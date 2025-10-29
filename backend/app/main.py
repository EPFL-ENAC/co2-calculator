"""FastAPI application entry point."""

import logging

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    description="""
    CO2 Calculator API with hierarchical authorization using Open Policy Agent.
    
    ## Features
    
    * **JWT Authentication** - Secure token-based authentication
    * **OPA Authorization** - Fine-grained access control with Open Policy Agent
    * **RBAC** - Role-based access control for users
    * **Multi-tenancy** - Support for multiple EPFL units
    * **RESTful API** - Clean and consistent API design
    
    ## Authorization Model
    
    The API uses OPA (Open Policy Agent) to make authorization decisions:
    
    1. User authenticates and receives JWT token
    2. Each request includes JWT token in Authorization header
    3. Backend validates JWT and extracts user context
    4. Service layer queries OPA with user context and action
    5. OPA returns decision with optional filters
    6. Backend applies filters to database queries
    7. Only authorized data is returned
    
    ## Roles
    
    * **admin** - Full access to resources in their unit
    * **unit_admin** - Manage unit resources
    * **user** - Basic user access
    * **resource.create** - Permission to create resources
    """,
)
# NO CORS origins configured allowed on this instance


# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"OPA enabled: {settings.OPA_ENABLED}")
    logger.info(f"OPA URL: {settings.OPA_URL}")

    # Initialize database (in production, use Alembic migrations)
    if settings.DEBUG:
        logger.warning("Debug mode: Database tables will be auto-created")
        from app.db import init_db

        init_db()


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info(f"Shutting down {settings.APP_NAME}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
