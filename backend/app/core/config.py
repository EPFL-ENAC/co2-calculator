"""Application configuration using Pydantic settings."""

from enum import Enum
from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class RoleProviderType(str, Enum):
    """Backend implementation selection for where app roles come from."""

    JWT = "jwt"
    ACCRED = "accred"
    TEST = "test"


class UnitProviderType(str, Enum):
    """Backend implementation selection for where institutional units come from."""

    DATABASE = "database"
    ACCRED = "accred"
    TEST = "test"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings must be provided via environment variables or .env file.
    See .env.example for reference configuration.
    """

    # General to avoid B104:hardcoded_bind_all_interfaces
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    WORKERS: int = 1

    # Application
    APP_NAME: str = "CO2 Calculator API"
    APP_VERSION: str = "0.1.0"
    # SECURITY: must stay False on stage/prod. DEBUG drops the session cookie's
    # Secure flag (main.py) and registers the /login-test auth bypass (auth.py).
    # One image ships to every env; DEBUG is set per-platform in gitops
    # (dev=true, stage/prod=false). Never flip this default to True.
    DEBUG: bool = False
    LOCAL_ENVIRONMENT: bool = Field(
        default=False,
        description=(
            "Set to True for local development environment. Double-duty: also "
            "gates the boot-time security check (`assert_security_settings` in "
            "app/main.py) that fails closed when credential-encryption/SSRF "
            "settings are missing. Forced true for the whole test suite via "
            "pytest-env in pyproject.toml."
        ),
    )
    API_DOCS_PREFIX: str = "/api"
    API_VERSION: str = "/v1"

    # Database Configuration
    # Provide full DB_URL directly (takes precedence)
    DB_URL: str | None = Field(
        default="sqlite+aiosqlite:///./co2_calculator.db",
        description="""
            Full database URL. If not set, defaults to SQLite.
            Example: sqlite+aiosqlite:///./co2_calculator.db
            """,
    )
    # #1723 — explicit pool sizing (skipped for sqlite, see app/db.py).
    # Without these SQLAlchemy defaults to pool_size=5/max_overflow=10,
    # which is the exact "QueuePool limit of size 5 overflow 10 reached"
    # error a factor CSV upload's emission_recalc fan-out used to hit.
    DB_POOL_SIZE: int = Field(
        default=10,
        ge=1,
        description=(
            "Base number of pooled async DB connections per pod (ignored "
            "for sqlite). Sized alongside MAX_CONCURRENT_JOBS: each "
            "running job holds 1-2 connections (runner job_session + "
            "handler data_session) for its whole runtime."
        ),
    )
    DB_MAX_OVERFLOW: int = Field(
        default=10,
        ge=0,
        description=(
            "Extra connections allowed beyond DB_POOL_SIZE under burst "
            "load (ignored for sqlite). DB_POOL_SIZE + DB_MAX_OVERFLOW is "
            "the hard cap on connections one pod can open."
        ),
    )
    DB_POOL_TIMEOUT: int = Field(
        default=30,
        ge=1,
        description=(
            "Seconds a request waits for a pooled connection before "
            "raising QueuePool timeout (ignored for sqlite)."
        ),
    )

    # Files Storage Configuration
    # S3 if configured, or local filesystem otherwise
    FILES_STORAGE_PATH: str = Field(
        default="./files_storage",
        description="Path to local file storage directory",
    )
    # Optional encryption for files, both key and salt must be set to enable
    FILES_ENCRYPTION_KEY: str = Field(
        default="",
        description=(
            "Encryption key for file storage (optional). "
            "This MUST be a strong, randomly generated secret and must never be "
            "committed to source control. Provide it via environment variables or "
            "a secret manager only. The key is expected to be a URL-safe base64 "
            "encoded value representing at least 32 bytes of cryptographic key "
            "material."
        ),
    )
    FILES_ENCRYPTION_SALT: str = Field(
        default="",
        description=(
            "Salt for file encryption key derivation (required if key is set). "
            "This should also be a strong, randomly generated secret value, kept "
            "out of source control and provided via environment variables or a "
            "secret manager. Use a URL-safe base64 encoded string (at least 16 "
            "bytes) and keep it stable for the lifetime of the encrypted data."
        ),
    )
    # S3 Configuration (optional, for using S3-compatible storage)
    S3_ENDPOINT_PROTOCOL: str = Field(
        default="https",
        description="S3 endpoint protocol (e.g., https)",
    )
    S3_ENDPOINT_HOSTNAME: str = Field(
        default="",
        description="S3 endpoint hostname (leave empty if not using S3)",
    )
    S3_ACCESS_KEY_ID: str = Field(
        default="",
        description="S3 access key ID (leave empty if not using S3)",
    )
    S3_SECRET_ACCESS_KEY: str = Field(
        default="",
        description="S3 secret access key (leave empty if not using S3)",
    )
    S3_REGION: str = Field(
        default="",
        description="S3 region (leave empty if not using S3)",
    )
    S3_BUCKET: str = Field(
        default="",
        description="S3 bucket name (leave empty if not using S3)",
    )
    S3_PATH_PREFIX: str = Field(
        default="",
        description="S3 path prefix (leave empty if not using S3)",
    )
    # Maximum file size for uploads (in megabytes)
    FILES_MAX_SIZE_MB: int = Field(
        default=100,
        description="Maximum file size in megabytes for uploads",
    )

    # Security - REQUIRED outside local dev, enforced by assert_security_settings
    # (app/main.py). Two separate signing keys, two separate blast radii:
    # rotating one must not invalidate the other.
    JWT_HMAC_KEY: str = Field(
        default="",
        description=(
            "HMAC signing key for access/refresh JWTs (app/core/security.py). "
            "REQUIRED. Must never be committed to source control — provide via "
            "environment variables or a secret manager only."
        ),
    )
    SESSION_HMAC_KEY: str = Field(
        default="",
        description=(
            "HMAC signing key for Starlette's SessionMiddleware, which signs "
            "the short-lived (60s) cookie used mid-OAuth-flow only (app/main.py). "
            "REQUIRED. Deliberately separate from JWT_HMAC_KEY so rotating one "
            "signing domain never invalidates the other."
        ),
    )

    ALGORITHM: str = "HS256"

    # Logging
    LOG_LEVEL: str = "INFO"

    # CO2 Calculation Constants
    HOURS_PER_WEEK: int = Field(
        default=168,
        description="Total hours per week for equipment usage calculation",
    )
    WEEKS_PER_YEAR: int = Field(
        default=52,
        description="Weeks per year for annual CO2 calculation",
    )
    DEFAULT_ACTIVE_USAGE_HOURS_PER_WEEK: int = Field(
        default=12,
        description="Fallback equipment active usage hours per week when neither "
        "the prior year nor a matching factor provides a value",
    )
    DEFAULT_STANDBY_USAGE_HOURS_PER_WEEK: int = Field(
        default=156,
        description="Fallback equipment standby usage hours per week when neither "
        "the prior year nor a matching factor provides a value",
    )

    # CO2 Calculation Constants
    CO2_PER_KM_KG: float = Field(
        default=0.2996,
        gt=0,
        description="CO2 per km in kg",
    )

    # Loki (optional)
    LOKI_ENABLED: bool = False
    LOKI_URL: str | None = None  # e.g. http://loki:3100
    LOKI_TENANT_ID: str | None = None  # X-Scope-OrgID if multi-tenant
    LOKI_TIMEOUT: float = 2.0  # seconds
    # default job label; falls back to APP_NAME
    LOKI_LABEL_JOB: str | None = None
    LOKI_LABEL_ENV: str | None = None  # e.g. dev|staging|prod

    # TRAVEL API TABLEAU CONFIGURATION
    # Connection credentials (server_url, site, username, connected-app) are
    # stored per-connector in the DB (ConnectorConnection, #1552); only the
    # operational knobs below stay in settings.
    TABLEAU_VERIFY_SSL: str = "true"
    TABLEAU_REQUEST_TIMEOUT_SECONDS: str = "300"
    TABLEAU_REST_MIN_API_VERSION: str = "2.4"
    TABLEAU_MAX_FIELDS: int = 50

    # Credential encryption (required to store connection secrets)
    CREDENTIALS_ENCRYPTION_KEY: str = Field(
        default="",
        description=(
            "URL-safe base64 secret (>=32 bytes) used to derive the Fernet "
            "key that encrypts stored connection secrets. Provide via env or "
            "a secret manager only; never commit."
        ),
    )
    CREDENTIALS_ENCRYPTION_SALT: str = Field(
        default="",
        description=(
            "URL-safe base64 salt (>=16 bytes) for credential key derivation. "
            "Keep stable for the lifetime of the encrypted data."
        ),
    )
    # SSRF guard: host suffixes a connection server_url may target.
    CONNECTOR_ALLOWED_HOST_SUFFIXES: str = Field(
        default="",
        description=(
            "Comma-separated host suffixes an API-connection server_url may "
            "target (e.g. 'epfl.ch'). SSRF guard; empty fails closed."
        ),
    )

    # Role/Unit provider selection — where do app roles / institutional units
    # come from. No default: invalid or missing config fails at startup
    # rather than silently picking a provider.
    ROLE_PROVIDER_TYPE: RoleProviderType = Field(
        description=(
            "Where app roles come from: 'jwt' (parse from JWT claims), "
            "'accred' (EPFL Accred API), or 'test' (for testing/development)."
        ),
    )
    UNIT_PROVIDER_TYPE: UnitProviderType = Field(
        description=(
            "Where institutional units come from: 'database' (local DB), "
            "'accred' (EPFL Accred API), or 'test' (for testing/development)."
        ),
    )

    # EPFL Accred API Configuration — required whenever ROLE_PROVIDER_TYPE
    # and/or UNIT_PROVIDER_TYPE is 'accred', enforced at app boot by
    # assert_accred_settings (app/main.py), NOT here: Settings is also
    # built by non-app contexts (alembic migrations) that never call Accred.
    # Shared by both RoleProvider and UnitProvider — Accred is one API
    # serving both concerns, so the config is not role- or unit-specific.
    ACCRED_API_BASE_URL: str | None = Field(
        default=None,
        description="EPFL Accred API base URL (e.g., https://api.epfl.ch/v1/accreds)",
    )
    ACCRED_API_USERNAME: str | None = Field(
        default=None,
        description="EPFL Accred API username for Basic Auth",
    )
    ACCRED_API_KEY: str | None = Field(
        default=None,
        description="EPFL Accred API key/password for Basic Auth",
    )
    ACCRED_AUTHORIZATION_HEALTHCHECK_URL: str | None = Field(
        default=None,
        description=(
            "Accred authorization-readiness check URL for /ready — confirms "
            "backend credentials can reach Accred and read the expected "
            "authorization data. Not a generic API health URL."
        ),
    )

    # OAuth/OIDC Configuration (supports Keycloak, Entra ID, or other OIDC providers)
    OAUTH_CLIENT_ID: str | None = Field(
        default=None,
        description="OAuth2/OIDC Client ID",
    )
    OAUTH_CLIENT_SECRET: str | None = Field(
        default=None,
        description="OAuth2/OIDC Client Secret",
    )
    OAUTH_ISSUER_URL: str | None = Field(
        default=None,
        description=(
            "OAuth2/OIDC Issuer URL (base URL). "
            "Examples: "
            "- Keycloak: https://keycloak.example.com/realms/your-realm "
            "- Entra ID: https://login.microsoftonline.com/{tenant-id}/v2.0 "
            "The well-known configuration endpoint will be automatically appended."
        ),
    )
    # not used directly, but can be useful for some providers
    OAUTH_TENANT_ID: str | None = Field(
        default=None,
        description="OAuth2/OIDC Tenant ID or Realm (if applicable)",
    )
    OAUTH_SCOPE: str | None = Field(
        default="openid profile email",
        description="OAuth2/OIDC scopes to request (space-separated)",
    )
    OAUTH_COOKIE_PATH: str | None = Field(
        default="/",
        description="OAuth2/OIDC cookie path",
    )
    COOKIE_SECURE: bool = Field(
        default=True,
        description=(
            "Set the `Secure` attribute on auth cookies. Default true (correct "
            "for prod HTTPS). MUST be overridden to false for local HTTP dev — "
            "Safari and httpx-based clients refuse to re-send a Secure cookie "
            "over plain http://localhost, which silently breaks /me, /refresh, "
            "and /login-test. See .env.example. Independent of DEBUG so a debug "
            "build behind a TLS terminator can still mint Secure cookies."
        ),
    )

    # Session lifetimes — see issue #949. Tuned for an internal EPFL app
    # behind Entra SSO + httpOnly+secure+samesite cookies; 8h access / 24h
    # refresh keeps a working day usable while still capping idle sessions.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_HOURS: int = 24
    # Frontend URL for redirects
    FRONTEND_URL: str = Field(
        default="http://localhost:9000",
        description="Frontend application URL for OAuth redirects",
    )
    CSRF_ADDITIONAL_ORIGINS: str = Field(
        default="",
        description=(
            "Comma-separated origins accepted on cookie-authenticated writes, "
            "beyond the one derived from FRONTEND_URL (#89). Empty in every "
            "normal deployment; exists so a genuine second frontend host does "
            "not require a code change."
        ),
    )
    FORMULA_VERSION_SHA256_SHORT: str = Field(
        default="",
        description="SHA256 short hash of formula (e.g., git commit)",
    )

    # `@property` under `@computed_field` (unlike `oauth_metadata_url` below):
    # callers iterate this, and without it the type checker sees a bound method.
    @computed_field
    @property
    def csrf_additional_origins(self) -> list[str]:
        """Split CSRF_ADDITIONAL_ORIGINS, dropping blanks from stray commas."""
        return [o.strip() for o in self.CSRF_ADDITIONAL_ORIGINS.split(",") if o.strip()]

    @computed_field
    def oauth_metadata_url(self) -> str:
        """Build OIDC discovery URL from issuer URL."""
        if self.OAUTH_ISSUER_URL:
            # Ensure no trailing slash
            issuer = self.OAUTH_ISSUER_URL.rstrip("/")
            return f"{issuer}/.well-known/openid-configuration"
        return ""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # .env wins over real env vars: a stray shell `export DB_URL=...`
        # left over from testing shouldn't silently outrank a fixed .env.
        # Stage/prod ship no .env file, so real env vars (helm/k8s) still apply there.
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

    # NOTE: Elastic SEARCH OPDO/27001/27701 compatiblity

    ELASTICSEARCH_HOSTS: str = Field(
        default="https://locahost:9200",
        description="Comma-separated list of Elasticsearch hosts",
    )
    ELASTICSEARCH_INDEX: str = Field(
        default="UNDEFINED_INDEX", description="Elasticsearch index name"
    )
    ELASTICSEARCH_ID: str = Field(
        default="", description="Elasticsearch ID for authentication"
    )
    ELASTICSEARCH_API_KEY: str = Field(
        default="", description="Elasticsearch API key for authentication"
    )
    # // use a secret in kube to mount the path
    ELASTICSEARCH_CA_CERT: str = Field(
        default="/etc/ssl/certs/http_ca_test.crt",
        description="Path to Elasticsearch CA certificate",
    )
    ELASTICSEARCH_TIMEOUT: int = Field(
        default=30, description="Elasticsearch timeout in seconds"
    )
    ELASTICSEARCH_MAX_RETRIES: int = Field(
        default=3, description="Maximum number of Elasticsearch retries"
    )
    ELASTICSEARCH_RETRY_ON_TIMEOUT: bool = Field(
        default=True, description="Retry Elasticsearch on timeout"
    )

    # Audit Sync Filtering Configuration
    AUDIT_SYNC_SKIP_ENTITY_TYPES: str = Field(
        default="User",
        description=(
            "Comma-separated list of entity types to skip during sync "
            "(e.g., 'User,Organization')"
        ),
    )
    AUDIT_SYNC_SKIP_HANDLER_IDS: str = Field(
        default="csv_ingestion",
        description=(
            "Comma-separated list of handler IDs to skip during "
            "sync (e.g., 'csv_ingestion,api_import')"
        ),
    )

    IT_RESEARCH_FACILITY_IDS: str = Field(
        default="",
        description=(
            "Comma-separated list of research facility IDs whose emissions "
            "are classified as IT facilities (e.g., '0616,1027,1902')"
        ),
    )

    # Background job safety (Plan 310A + auto-recovery sweep, PR #998)
    STALE_JOB_TIMEOUT_MINUTES: int = Field(
        default=5,
        description=(
            "Minutes before a RUNNING job is considered stale.  Doubles as "
            "the auto-recovery sweep's threshold: jobs whose ``locked_at`` "
            "is older than this are reset to NOT_STARTED (or marked "
            "FINISHED+ERROR if attempts >= max_attempts).  The 310-C runner "
            "heartbeats ``locked_at`` every quarter of this window, so the "
            "value bounds *crash recovery latency*, not job runtime — a "
            "healthy long-running job is never falsely recovered.  Keep it "
            "high enough that transient DB outages shorter than the window "
            "don't make a live runner self-abort (see ``_heartbeat_loop``); "
            "5 min = 75s heartbeats and ~5-6 min worst-case recovery after "
            "a pod dies mid-job (stage incident 2026-07-17: the old 60 min "
            "default left a killed aggregation invisible for an hour)."
        ),
    )
    # #1723 — bounds every run_job dispatch path (poller sweep, chain_job
    # fan-out, and endpoint-triggered fire_and_forget), not just the
    # poller. One asyncio.Semaphore in app.tasks.runner, acquired BEFORE
    # the DB claim: a queued job holds no claim, so an idle replica's
    # poller can pick it up instead of it sitting stuck behind a busy
    # pod. Fixes the QueuePool exhaustion a factor CSV upload's
    # emission_recalc fan-out used to trigger.
    MAX_CONCURRENT_JOBS: int = Field(
        default=4,
        ge=1,
        description=(
            "Max background jobs this pod runs at once, across every "
            "dispatch path (poller, chain_job, endpoint fire-and-forget). "
            "At 2-3 replicas this caps fleet-wide running jobs at 8-12."
        ),
    )
    RUN_BACKGROUND_POLLER: bool = Field(
        default=True,
        description="Whether to run the in-process safety poller",
    )
    DISPATCH_JOBS_INLINE: bool = Field(
        default=True,
        description=(
            "Whether HTTP endpoints execute the job they just created "
            "(fire_and_forget_or_defer_to_poller) or leave it NOT_STARTED "
            "for a poller elsewhere to pick up (#2050 Track B). Separate "
            "from RUN_BACKGROUND_POLLER on purpose: the test suite already "
            "disables the poller everywhere while still asserting inline "
            "dispatch fires, and a worker-split deployment needs the "
            "opposite pairing on its API pods (dispatch off, and no "
            "poller of its own either). False with no other pod running "
            "the poller leaves jobs stuck NOT_STARTED forever — the Helm "
            "chart's worker.enabled must gate both flags together so that "
            "combination can't be expressed."
        ),
    )
    POLLER_INTERVAL_SECONDS: int = Field(
        default=2,
        ge=1,
        description=(
            "Seconds between safety-poller sweeps.  Each sweep is one "
            "indexed ``SELECT … FOR UPDATE SKIP LOCKED`` plus the "
            "stuck-RUNNING recovery query, so a tight cadence is cheap; "
            "2s keeps orphan-recovery latency near-interactive after a "
            "pod crash.  Raise on deployments where DB connection budget "
            "is tighter than recovery latency."
        ),
    )
    POLLER_BATCH_LIMIT: int = Field(
        default=100,
        ge=1,
        description=(
            "Max NOT_STARTED jobs dispatched per poller sweep.  "
            "``SKIP LOCKED`` keeps multi-pod sweeps from double-"
            "dispatching; the limit only bounds how many in-process "
            "run_job tasks one sweep can fan out at once."
        ),
    )
    INGEST_COPY_BATCH_SIZE: int = Field(
        default=50_000,
        ge=1,
        description=(
            "Rows per batch when bulk CSV ingest writes ``data_entries`` "
            "via PostgreSQL ``COPY … FROM STDIN``.  Bounds both the "
            "in-memory row buffer and the size of each COPY statement; "
            "50k keeps a 512Mi pod comfortable while amortising per-row "
            "INSERT overhead away."
        ),
    )

    # #1236 Phase 3 — pipeline status reconciliation cron.
    RUN_PIPELINE_RECONCILER: bool = Field(
        default=True,
        description=(
            "Whether to run the in-process pipeline-status reconciliation "
            "sweep.  The sweep is the durable backstop for the runner's "
            "post-finish_job isolated status write — that write log-and-"
            "skips on any DB error, so without this cron a missed write "
            "leaves a pipeline showing the wrong status until the next "
            "manual reconcile.  Keep on in production; flip off only for "
            "diagnostic single-process runs where you want the table to "
            "lag visibly."
        ),
    )
    PIPELINE_RECONCILER_INTERVAL_SECONDS: int = Field(
        default=60,
        ge=10,
        description=(
            "Seconds between pipeline reconciliation sweeps.  60s = "
            "stale window ≤ ~1 minute for the rare case where the "
            "runner's isolated write log-and-skipped.  The sweep is "
            "indexed on ``pipelines.status`` and commits per pipeline; "
            "tighter cadence has no measured benefit."
        ),
    )

    # #1080 sprint-9 — pod heartbeat for the workers view.
    RUN_POD_HEARTBEAT: bool = Field(
        default=True,
        description=(
            "Whether to run the in-process pod heartbeat writer.  The "
            "loop INSERTs (or UPDATEs on conflict) a ``pods`` row for "
            "the current pod's POD_ID and refreshes ``last_heartbeat_at`` "
            "every ``POD_HEARTBEAT_INTERVAL_SECONDS``.  Backs the "
            "``GET /v1/sync/workers`` endpoint that surfaces 'who's "
            "claiming work right now' — the diagnostic gap that let a "
            "local branch + stage DB conflict silently stall recalcs "
            "(2026-05-21)."
        ),
    )
    POD_HEARTBEAT_INTERVAL_SECONDS: int = Field(
        default=30,
        ge=5,
        description=(
            "Seconds between pod heartbeat refreshes.  The workers "
            "endpoint considers a pod live when its "
            "``last_heartbeat_at`` is within ``2 ×`` this interval, so "
            "30s = dead pods drop off the live list within ~1 minute."
        ),
    )
    # #2049 — background DB health poller, so /ready and /healthz do zero
    # I/O of their own (#2050 A1 bounded the per-request check; this
    # removes it entirely).
    RUN_DB_HEALTH_POLLER: bool = Field(
        default=True,
        description=(
            "Whether to run the in-process DB health poller. Mainly a "
            "test/diagnostic kill-switch, not a real production lever: "
            "/ready has no other source of DB status, so leaving this "
            "off on a pod that serves /ready makes it permanently 503 "
            "(fail-closed, by design — not something to work around with "
            "a fallback check)."
        ),
    )
    DB_HEALTH_CHECK_INTERVAL_SECONDS: int = Field(
        default=1,
        ge=1,
        description=(
            "Seconds between background SELECT 1 checks. /ready and "
            "/healthz read the cached result of the last check rather "
            "than querying the DB themselves."
        ),
    )
    DB_HEALTH_SLOW_THRESHOLD_MS: int = Field(
        default=100,
        ge=1,
        description=(
            "SELECT 1 latency above this is reported as 'sluggish' in "
            "/healthz's body. Does not affect /ready — a slow-but-"
            "reachable DB still serves traffic; failing readiness on "
            "shared DB latency would take every pod unready at once."
        ),
    )

    # Build provenance — populated by CI on deploy.  Optional in dev.
    GIT_SHA: str | None = Field(
        default=None,
        description=(
            "Commit SHA the running code was built from.  Surfaced via "
            "the workers view so an operator can see at a glance when "
            "two pods are on different revisions — the local+stage "
            "scenario that motivated this telemetry."
        ),
    )

    # Year Configuration Bounds (issue #1204)
    MIN_CONFIGURABLE_YEAR: int = Field(
        default=2025,
        description=(
            "Earliest year backoffice can create a YearConfiguration for. "
            "``POST /year-configuration/{year}`` rejects anything below this "
            "floor; the GET response also echoes it so the frontend year "
            "dropdown stays in sync without a hardcoded copy of its own."
        ),
    )
    APP_MIN_REDUCTION_YEAR: int = Field(
        default=1990,
        description=(
            "Earliest reference year a reduction objective goal may use. "
            "Echoed in the year configuration response for the frontend."
        ),
    )
    APP_MAX_REDUCTION_YEAR: int = Field(
        default=2050,
        description=(
            "Latest reference year a reduction objective goal may use. "
            "Echoed in the year configuration response for the frontend."
        ),
    )

    EXPLORE_TTL_SECONDS: int = Field(
        default=24 * 60 * 60,
        ge=1,
        description=(
            "Seconds before a Simulator Explore report is considered stale. "
            "A GET past this age still returns the stale report immediately "
            "but schedules a background task that deletes it and seeds a "
            "fresh empty one."
        ),
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    # ROLE_PROVIDER_TYPE/UNIT_PROVIDER_TYPE have no default (intentional —
    # missing config must fail startup); pydantic-settings actually sources
    # them from the environment/.env file at runtime.
    return Settings()
