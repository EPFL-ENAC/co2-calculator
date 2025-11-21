"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run on application startup."""
    logger.info(
        "Starting application",
        extra={
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "api_version": settings.API_VERSION,
            "frontend_url": settings.FRONTEND_URL,
            "api_docs_prefix": settings.API_DOCS_PREFIX,
            "debug": settings.DEBUG,
        },
    )
    if settings.LOKI_ENABLED:
        logger.info("Loki enabled", extra={"loki_enabled": settings.LOKI_ENABLED})

    # Initialize database (in production, use Alembic migrations)
    if settings.DEBUG:
        logger.warning("Debug mode: Database tables will be auto-created")
        from app.db import init_db

        await init_db()
    yield

    """Run on application shutdown."""
    logger.info("Shutdown complete", extra={settings.APP_NAME: settings.APP_VERSION})


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    # Prevent automatic redirect on trailing slash: Mandatory double slash handling
    redirect_slashes=False,
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
    lifespan=lifespan,
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
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")


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


@app.get("/health", response_class=JSONResponse)
async def health():
    """Health check endpoint."""
    details = {}

    # Database check
    try:
        from app.db import get_db_session  # Adjust import as needed

        session = await get_db_session()
        async with session:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = "error"
        details["db_error"] = str(e)

    # Accred (role_provider) check
    try:
        import httpx

        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(
                settings.ACCRED_API_HEALTH_URL,
                auth=(settings.ACCRED_API_USERNAME, settings.ACCRED_API_KEY),
            )
            if resp.status_code == 200:
                accred_status = "ok"
            else:
                accred_status = f"error ({resp.status_code})"
    except Exception as e:
        accred_status = "error"
        details["accred_error"] = str(e)

    healthy = db_status == "ok" and accred_status == "ok"
    status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "database": db_status,
            "accred": accred_status,
            "details": details,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
