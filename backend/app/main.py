"""FastAPI application entry point."""

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy.engine import make_url
from starlette.middleware.sessions import SessionMiddleware

from app.api.internal import router as internal_router
from app.api.router import api_router
from app.core.config import RoleProviderType, UnitProviderType, get_settings
from app.core.exception_handlers import permission_denied_handler
from app.core.exceptions import (
    InsufficientScopeError,
    PermissionDeniedError,
    RecordAccessDeniedError,
)
from app.core.logging import get_logger, setup_logging
from app.core.request_origin import RequestOriginMiddleware
from app.tasks._db_health import DBHealthState, get_db_health_state, is_fresh

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Get settings
settings = get_settings()


def assert_security_settings(settings) -> None:
    """Fail closed at boot outside local/dev when security settings are missing."""
    if settings.LOCAL_ENVIRONMENT:
        return
    missing = [
        name
        for name in (
            "JWT_HMAC_KEY",
            "SESSION_HMAC_KEY",
            "CREDENTIALS_ENCRYPTION_KEY",
            "CREDENTIALS_ENCRYPTION_SALT",
            "CONNECTOR_ALLOWED_HOST_SUFFIXES",
            # Empty values would leave make_files_store() unencrypted, writing
            # plaintext uploads to object storage with no error (#454).
            "FILES_ENCRYPTION_KEY",
            "FILES_ENCRYPTION_SALT",
        )
        if not getattr(settings, name)
    ]
    if missing:
        raise RuntimeError(f"Missing required security settings: {missing}")


def assert_accred_settings(settings) -> None:
    """Require Accred credentials at boot whenever a provider selects Accred.

    Enforced here rather than in Settings construction so non-app contexts
    that build Settings but never call Accred (alembic migrations) don't
    need the credentials.
    """
    uses_accred = (
        settings.ROLE_PROVIDER_TYPE == RoleProviderType.ACCRED
        or settings.UNIT_PROVIDER_TYPE == UnitProviderType.ACCRED
    )
    if not uses_accred:
        return
    missing = [
        name
        for name in ("ACCRED_API_BASE_URL", "ACCRED_API_USERNAME", "ACCRED_API_KEY")
        if getattr(settings, name) is None
    ]
    if missing:
        raise RuntimeError("Missing required Accred config: " + ", ".join(missing))


# DB hosts a local instance may poll without colliding with a deployed
# fleet: its own machine, or docker-compose's `postgres` service.
_LOCAL_DB_HOSTS = frozenset({None, "localhost", "127.0.0.1", "::1", "postgres"})


def assert_poller_isolation(settings) -> None:
    """Fail closed at boot when a local instance would claim a shared DB's jobs.

    #2220 root cause: a laptop running ``make dev`` with ``.env`` pointed at
    the dev database polled and claimed dev's ingestion jobs, then resolved
    their uploaded files against its own LocalFilesStore — every CSV move
    failed with "source no longer exists" while the file sat untouched in S3.
    """
    if not settings.LOCAL_ENVIRONMENT or not settings.RUN_BACKGROUND_POLLER:
        return
    if settings.DB_URL is None:
        return
    host = make_url(settings.DB_URL).host
    if host in _LOCAL_DB_HOSTS:
        return
    raise RuntimeError(
        f"LOCAL_ENVIRONMENT=True with RUN_BACKGROUND_POLLER=True against a "
        f"non-local database ({host}): this process would claim that "
        "deployment's jobs and fail their file moves (#2220). Set "
        "RUN_BACKGROUND_POLLER=False in backend/.env to work against a "
        "shared DB, or point DB_URL at localhost."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run on application startup."""
    assert_security_settings(settings)
    assert_accred_settings(settings)
    assert_poller_isolation(settings)

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

    # Plan 310-C: prime the runner's handler registry.  Bootstrap is
    # idempotent and lazy-imports the handler modules so audit_service's
    # early ``audit_sync_tasks`` import doesn't form a cycle through
    # ingestion provider factory + audit_service.
    from app.tasks.bootstrap import bootstrap_handlers

    bootstrap_handlers()

    # Start the safety poller (Plan 310A)
    if settings.RUN_BACKGROUND_POLLER:
        from app.tasks._pod_id import POD_ID
        from app.tasks._poller import poll_pending_jobs

        logger.info(f"Starting safety poller on pod {POD_ID}")
        app.state.poller_task = asyncio.create_task(poll_pending_jobs())

    # Start the pipeline reconciliation sweep (#1236 Phase 3) — durable
    # backstop for the runner's log-and-skip post-``finish_job`` write.
    if settings.RUN_PIPELINE_RECONCILER:
        from app.tasks._pipeline_reconciler import reconcile_pipeline_statuses_loop

        logger.info(
            "Starting pipeline reconciler (every %ss)",
            settings.PIPELINE_RECONCILER_INTERVAL_SECONDS,
        )
        app.state.pipeline_reconciler_task = asyncio.create_task(
            reconcile_pipeline_statuses_loop()
        )

    # Start the pod heartbeat writer (#1080 sprint-9) — registers
    # this pod in the ``pods`` table and refreshes its
    # ``last_heartbeat_at`` so the workers view can show "who's
    # claiming work right now".  Motivating incident: a dev branch
    # running locally against the stage DB silently collided with
    # the deployed stage app — no UI surfaced two pods.
    if settings.RUN_POD_HEARTBEAT:
        from app.tasks._pod_heartbeat import pod_heartbeat_loop

        logger.info(
            "Starting pod heartbeat (every %ss)",
            settings.POD_HEARTBEAT_INTERVAL_SECONDS,
        )
        app.state.pod_heartbeat_task = asyncio.create_task(pod_heartbeat_loop())

    # Start the background DB health poller (#2049) — /ready and /healthz
    # read its cached verdict instead of doing their own DB I/O.
    if settings.RUN_DB_HEALTH_POLLER:
        from app.tasks._db_health import db_health_check_loop

        logger.info(
            "Starting DB health poller (every %ss)",
            settings.DB_HEALTH_CHECK_INTERVAL_SECONDS,
        )
        app.state.db_health_task = asyncio.create_task(db_health_check_loop())

    # Start the event-loop lag probe (#2049 T5) — the only traffic-
    # independent measurement of whether the loop is blocked.
    if settings.RUN_EVENT_LOOP_LAG_PROBE:
        from app.tasks._event_loop_lag import event_loop_lag_probe_loop

        logger.info(
            "Starting event-loop lag probe (every %ss)",
            settings.EVENT_LOOP_LAG_PROBE_INTERVAL_SECONDS,
        )
        app.state.event_loop_lag_task = asyncio.create_task(event_loop_lag_probe_loop())

    yield

    # Cancel background tasks on shutdown
    task = getattr(app.state, "poller_task", None)
    if task:
        logger.info("Cancelling safety poller")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Safety poller cancelled successfully")
    reconciler_task = getattr(app.state, "pipeline_reconciler_task", None)
    if reconciler_task:
        logger.info("Cancelling pipeline reconciler")
        reconciler_task.cancel()
        try:
            await reconciler_task
        except asyncio.CancelledError:
            logger.info("Pipeline reconciler cancelled successfully")
    heartbeat_task = getattr(app.state, "pod_heartbeat_task", None)
    if heartbeat_task:
        logger.info("Cancelling pod heartbeat")
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            logger.info("Pod heartbeat cancelled successfully")
    db_health_task = getattr(app.state, "db_health_task", None)
    if db_health_task:
        logger.info("Cancelling DB health poller")
        db_health_task.cancel()
        try:
            await db_health_task
        except asyncio.CancelledError:
            logger.info("DB health poller cancelled successfully")
    event_loop_lag_task = getattr(app.state, "event_loop_lag_task", None)
    if event_loop_lag_task:
        logger.info("Cancelling event-loop lag probe")
        event_loop_lag_task.cancel()
        try:
            await event_loop_lag_task
        except asyncio.CancelledError:
            logger.info("Event-loop lag probe cancelled successfully")

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

    - **Roles are assigned** to users (e.g., principal, backoffice metier, super admin)
    - **Permissions are calculated** dynamically from roles at authentication
    - **Access control** is enforced at the route level using permissions
    - **Data filtering** is applied based on user scope (global, unit, own)

    ### Permission Structure

    Permissions follow a hierarchical dot-notation structure:

    * **backoffice.*** - One permission per backoffice page
        * `backoffice.reporting` (view, export) - Reporting (affiliation-scoped)
        * `backoffice.users` (view, edit, export) - User management
        * `backoffice.documentation` / `backoffice.ui_texts` (view, edit)
        * `backoffice.configuration` / `backoffice.pipeline_operations`
          (view, edit) - super admin only
        * `backoffice.logs` (view) - super admin only

    * **modules.*** - CO2 calculation modules (unit-scoped `…/<unit>`, or
      own-scoped `…/<unit>/own` for standard users)
        * `modules.headcount`, `modules.professional_travel`, `modules.equipment`,
          … (view, edit, sync)

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

    * **Global scope** (super admin) - See all data
    * **Unit scope** (principals) - See data for their assigned units
    * **Own scope** (standard users) - See only their own data

    ## Assigned Roles

    Users are assigned one or more of these roles. Permissions are calculated
    from role assignments:

    * **calco2.user.std** - Basic user with own-scope access
    * **calco2.user.principal** - Unit-level manager with unit-scope access
    * **calco2.backoffice.metier** - Backoffice administrator with reporting and
      data access
    * **calco2.backoffice.admin** - Super administrator with full system and backoffice
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


# CORS stays disabled on this instance, deliberately: with no CORS headers the
# browser preflights and then drops every JSON-body and PUT/PATCH/DELETE
# forgery. RequestOriginMiddleware below covers what preflights don't — see
# docs/src/implementation-plans/89-security-in-depth.md.

# Add this after creating the FastAPI app
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_HMAC_KEY,
    session_cookie="session",
    max_age=60,  # 1 minute - only needed during OAuth flow
    same_site="lax",
    https_only=not settings.DEBUG,
)

# Registered after SessionMiddleware so it runs *before* it (Starlette builds
# the stack outside-in from the last registration): a request rejected for its
# origin must not touch session state on the way out.
app.add_middleware(RequestOriginMiddleware)

# Register exception handlers for permission-based access control
app.add_exception_handler(PermissionDeniedError, permission_denied_handler)
app.add_exception_handler(InsufficientScopeError, permission_denied_handler)
app.add_exception_handler(RecordAccessDeniedError, permission_denied_handler)

# Include API router
app.include_router(api_router, prefix=settings.API_VERSION)

# Intra-cluster-only endpoints (#2258 follow-up) — deliberately outside
# settings.API_VERSION and never referenced by a Helm Route; see
# app.api.internal's module docstring for the trust boundary.
app.include_router(internal_router)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


def _fresh_db_state() -> DBHealthState | None:
    """Cached DB health verdict from the background poller (#2049), or
    None if it's never checked yet or gone stale (poller not ticking).
    Shared so /healthz and /ready can't drift on what "fresh" means.
    """
    state = get_db_health_state()
    if state is None or not is_fresh(
        state, interval_seconds=settings.DB_HEALTH_CHECK_INTERVAL_SECONDS
    ):
        return None
    return state


_DB_STATUS_DISPLAY = {"ok": "ok", "slow": "sluggish", "down": "unresponsive"}


@app.get("/healthz")
async def healthz():
    """Lightweight liveness check endpoint.

    Always 200 — liveness answers "is the process alive", not "is a
    dependency up" (#2049). The database field is informational only,
    read from the background DB health poller's cache: zero I/O on this
    path either way. Used by Kubernetes livenessProbe.
    """
    state = _fresh_db_state()
    content: dict[str, object] = {
        "status": "ok",
        "database": _DB_STATUS_DISPLAY.get(state.status if state else "", "unknown"),
    }
    if state is not None:
        content["database_latency_ms"] = round(state.latency_ms, 1)
    return JSONResponse(status_code=status.HTTP_200_OK, content=content)


@app.get("/ready", response_class=JSONResponse)
async def ready():
    """Readiness check endpoint.

    #2049: reads the background DB health poller's cached verdict — zero
    I/O of its own, so a saturated pool can no longer make this endpoint
    itself hang (#2050 A1 bounded that per-request check; this removes
    it). 503 when the DB is down, unchecked, or the poller has gone
    stale; 200 otherwise. A merely *slow* DB still passes — DB latency is
    shared state, so gating readiness on it would take every pod unready
    at once, turning "slow" into the very outage this endpoint exists to
    prevent. Used by Kubernetes readinessProbe.

    External provider health (Accred) lives in /health/deps (#2050 A1):
    it must never gate readiness — a blip there is EPFL's incident, not
    ours.
    """
    state = _fresh_db_state()
    healthy = state is not None and state.status != "down"
    status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    if not healthy:
        logger.warning(
            "Readiness check failed",
            extra={
                "healthy": healthy,
                "database_status": state.status if state else "unknown",
                "db_error": state.error if state else None,
            },
        )

    # db_error stays in the log above — returning it would leak stack
    # traces / connection strings to unauthenticated callers.
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "database": state.status if state else "unknown",
        },
    )


@app.get("/health/deps", response_class=JSONResponse)
async def health_deps():
    """Operator-facing external-dependency health (Accred).

    Not a Kubernetes probe target — Accred availability must never gate
    pod readiness (#2050 A1); a blip there is EPFL's incident, not ours.
    This reports the same signal for humans/monitoring instead, via a
    real status code (503 on failure) so alerting can key off it directly
    instead of parsing the body — safe here specifically because nothing
    routes this endpoint's status into a probe or the Service.
    """
    details = {}
    role_provider_status = "skipped"
    uses_accred = (
        settings.ROLE_PROVIDER_TYPE == RoleProviderType.ACCRED
        or settings.UNIT_PROVIDER_TYPE == UnitProviderType.ACCRED
    )
    if uses_accred and settings.ACCRED_AUTHORIZATION_HEALTHCHECK_URL:
        # assert_accred_settings() above already guarantees these are set
        # whenever Accred is in use; narrow locally so ty sees non-None types.
        if settings.ACCRED_API_USERNAME is None or settings.ACCRED_API_KEY is None:
            raise ValueError("ACCRED_API_USERNAME and ACCRED_API_KEY must be set")
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(
                    settings.ACCRED_AUTHORIZATION_HEALTHCHECK_URL,
                    auth=(settings.ACCRED_API_USERNAME, settings.ACCRED_API_KEY),
                )
                if resp.status_code == 200:
                    role_provider_status = "ok"
                else:
                    role_provider_status = f"error ({resp.status_code})"
        except Exception as e:
            role_provider_status = "error"
            details["role_provider_error"] = str(e)

    is_healthy = role_provider_status in ("skipped", "ok")
    status_code = (
        status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(
        status_code=status_code,
        content={"role_provider": role_provider_status, "details": details},
    )


def run_main():
    """Run the application using Uvicorn."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        workers=settings.WORKERS if not settings.DEBUG else 1,
    )


if __name__ == "__main__":
    run_main()
