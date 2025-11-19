"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)

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

    * **co2.user.std**: basic user
    * **co2.user.principal**: unit-level manager
    * **co2.user.secondary**: delegated unit manager (same permissions as principal)
    * **co2.backoffice.std**: back office restricted (treat as admin but unit-scoped)
    * **co2.backoffice.admin**: back office full (treat as cross-unit admin)
    * **co2.service.mgr**: system IT administrator (treat as unconditional allow)

    """,
    # Swagger UI lives at /api/docs externally, but /docs internally works too
    root_path=settings.API_DOCS_PREFIX,
)
# NO CORS origins configured allowed on this instance

# Add this after creating the FastAPI app
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="session",
    max_age=60,  # 1 minute - only needed during OAuth flow
    same_site="lax",
    https_only=not settings.DEBUG,
)

# Add Forwarded Headers Middleware to handle X-Forwarded-* headers
# because of load balancer / reverse proxy in front of the app that
# handles TLS termination
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="h")


# Include API router
app.include_router(api_router, prefix=settings.API_VERSION)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Running lifespan")
    """Run on application startup."""
    logger.info(
        "Starting application",
        extra={"app_name": settings.APP_NAME, "app_version": settings.APP_VERSION},
    )
    logger.info("Debug mode", extra={"debug": settings.DEBUG})
    logger.info("Loki enabled", extra={"loki_enabled": settings.LOKI_ENABLED})

    # Initialize database (in production, use Alembic migrations)
    if settings.DEBUG:
        logger.warning("Debug mode: Database tables will be auto-created")
        from app.db import init_db

        await init_db()
    yield

    """Run on application shutdown."""
    logger.info("Shutdown complete", extra={settings.APP_NAME: settings.APP_VERSION})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
