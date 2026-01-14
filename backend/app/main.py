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
    if settings.LOCAL_ENVIRONMENT:
        logger.warning("Local mode: Database tables will be auto-created")
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
    CO2 Calculator API with permission-based authorization using Open Policy Agent.

    ## Features

    * **JWT Authentication** - Secure token-based authentication
    * **Permission-Based Authorization** - Fine-grained access control with
      calculated permissions
    * **OPA Policies** - Policy-based resource filtering and access control
    * **Multi-tenancy** - Support for multiple EPFL units with scope-based
      data filtering
    * **RESTful API** - Clean and consistent API design

    ## Permission-Based Authorization

    The API uses a permission-based authorization model where:

    - **Roles are assigned** to users (e.g., principal, secondary, backoffice admin)
    - **Permissions are calculated** dynamically from roles at authentication
    - **Access control** is enforced at the route level using permissions
    - **Data filtering** is applied based on user scope (global, unit, own)

    ### Permission Structure

    Permissions follow a hierarchical dot-notation structure:

    * **backoffice.*** - Administrative features
        * `backoffice.users` (view, edit) - User management
        * `backoffice.files` (view) - File storage access
        * `backoffice.access` (view) - Full backoffice access

    * **modules.*** - CO2 calculation modules
        * `modules.headcount` (view, edit) - Headcount data
        * `modules.professional_travel` (view, edit, export) - Travel records
        * `modules.equipment` (view, edit) - Equipment tracking
        * `modules.surface` (view, edit) - Surface data

    * **system.*** - System-level routes
        * `system.routes` (view) - System route access

    ### Permission Actions

    Each permission supports different actions:
    - **view** - Read access to resources
    - **edit** - Create, update, and delete operations
    - **export** - Data export capabilities

    ### How Permissions Work

    1. User authenticates via `/api/v1/auth/login` and receives JWT token
    2. JWT token contains user information and assigned roles
    3. On each request, permissions are calculated from roles
    4. Routes use `require_permission("path.resource", "action")` decorator
    5. If permission denied, returns 403 with specific error message
    6. Data queries are filtered by user scope (global/unit/own)

    ### Example Permission Check

    ```python
    @router.get("/headcounts")
    async def get_headcounts(
        user: User = Depends(require_permission("modules.headcount", "view"))
    ):
        # Only users with modules.headcount.view permission can access
        # Data is filtered by scope: global, unit, or own
    ```

    ## Authorization Model with OPA

    The API uses OPA (Open Policy Agent) patterns for authorization decisions:

    1. **Route-level permission checks** - Enforced via `require_permission()`
       decorator
    2. **Service-level data filtering** - Applied via `get_data_filters()`
       based on scope
    3. **Resource-level access control** - Checked via `check_resource_access()`
       for individual resources

    ### Scope-Based Data Filtering

    Data access is automatically filtered based on user scope:

    * **Global scope** (backoffice admin, service manager) - See all data
    * **Unit scope** (principals, secondaries) - See data for their assigned units
    * **Own scope** (standard users) - See only their own data

    ## Assigned Roles

    Users are assigned one or more of these roles. Permissions are calculated
    from role assignments:

    * **co2.user.std** - Basic user with own-scope access
    * **co2.user.principal** - Unit-level manager with unit-scope access
    * **co2.user.secondary** - Delegated unit manager (same permissions as principal)
    * **co2.backoffice.std** - Back office restricted with unit-scope admin access
    * **co2.backoffice.admin** - Back office administrator with global-scope access
    * **co2.service.mgr** - System IT administrator with full access

    See permission documentation for detailed role-to-permission mapping.

    ## 403 Error Responses

    When a user lacks required permissions, the API returns a 403 Forbidden response:

    ```json
    {
        "detail": "Permission denied: modules.headcount.edit required"
    }
    ```

    ### Common Causes

    * **Missing permission** - User's roles don't grant the required permission
    * **Insufficient scope** - User has permission but wrong scope
      (e.g., different unit)
    * **Resource restrictions** - Business rules prevent access
      (e.g., API trips are read-only)

    ### Requesting Access

    To gain additional permissions:
    1. Contact your unit principal or backoffice administrator
    2. Request the specific permission needed (shown in error message)
    3. Administrator can assign appropriate role via
       `/api/v1/backoffice/users` endpoints

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
            from sqlmodel import text

            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = "error"
        details["db_error"] = str(e)

    # Role provider health check
    if (settings.PROVIDER_PLUGIN != "accred") or (not settings.ACCRED_API_HEALTH_URL):
        role_provider_status = "skipped"
    else:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(
                    settings.ACCRED_API_HEALTH_URL,
                    auth=(settings.ACCRED_API_USERNAME, settings.ACCRED_API_KEY),
                )
                if resp.status_code == 200:
                    role_provider_status = "ok"
                else:
                    role_provider_status = f"error ({resp.status_code})"
        except Exception as e:
            role_provider_status = "error"
            details["role_provider_error"] = str(e)

    healthy = db_status == "ok"
    status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    log = logger.info if healthy else logger.warning
    log(
        "Health check",
        extra={
            "healthy": healthy,
            "database_status": db_status,
            "role_provider": role_provider_status,
            "details": details,
        },
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "database": db_status,
            "role_provider": role_provider_status,
            "details": details,
        },
    )


def run_main():
    """Run the application using Uvicorn."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    run_main()
