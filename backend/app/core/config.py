"""Application configuration using Pydantic settings."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings must be provided via environment variables or .env file.
    See .env.example for reference configuration.
    """

    # Application
    APP_NAME: str = "CO2 Calculator API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOCAL_ENVIRONMENT: bool = Field(
        default=False, description="Set to True for local development environment"
    )
    API_DOCS_PREFIX: str = "/api"
    API_VERSION: str = "/v1"

    # Database Configuration
    # Option 1: Provide full DB_URL directly (takes precedence)
    DB_URL: Optional[str] = Field(
        default=None,
        description="""
            Full database URL. If not set, defaults to SQLite
            or constructed PostgreSQL URL based on other settings: DB_*
            """,
    )

    # Option 2: Provide PostgreSQL connection details (optional, for PostgreSQL)
    DB_USER: Optional[str] = Field(
        default=None, description="Database user (optional, for PostgreSQL)"
    )
    DB_PASSWORD: Optional[str] = Field(
        default=None, description="Database password (optional, for PostgreSQL)"
    )
    DB_NAME: Optional[str] = Field(
        default=None, description="Database name (optional, for PostgreSQL)"
    )

    # necessary to build the DB URL if DB_URL is not provided
    DB_HOST: Optional[str] = Field(
        default=None, description="Database host (optional, for PostgreSQL)"
    )
    DB_PORT: Optional[int] = Field(
        default=None, description="Database port (optional, for PostgreSQL)"
    )

    @computed_field
    def db_url(self) -> str:
        """
        Get the database URL.

        Priority:
        1. If DB_URL is explicitly set, use it
        2. If DB_USER, DB_PASSWORD, DB_HOST, DB_NAME are all set, build PostgreSQL URL
        3. Otherwise, default to SQLite
        """
        # If DB_URL is explicitly provided, use it
        if self.DB_URL:
            return self.DB_URL

        # If PostgreSQL credentials are provided, build the URL
        if all(
            [self.DB_USER, self.DB_PASSWORD, self.DB_HOST, self.DB_PORT, self.DB_NAME]
        ):
            return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?async_fallback=True"

        # Default to SQLite for local development
        return "sqlite+aiosqlite:///./co2_calculator.db"

    # Security - REQUIRED in production
    SECRET_KEY: str = Field(
        default="CHANGE_ME_TO_A_SECURE_RANDOM_VALUE",
        description="Secret key for JWT encoding/decoding (REQUIRED)",
    )

    ALGORITHM: str = "HS256"

    # OPA Configuration
    OPA_URL: str = "http://localhost:8181"
    OPA_TIMEOUT: float = 1.0
    OPA_ENABLED: bool = False

    # Logging
    LOG_LEVEL: str = "INFO"

    # Loki (optional)
    LOKI_ENABLED: bool = False
    LOKI_URL: Optional[str] = None  # e.g. http://loki:3100
    LOKI_TENANT_ID: Optional[str] = None  # X-Scope-OrgID if multi-tenant
    LOKI_TIMEOUT: float = 2.0  # seconds
    LOKI_LABEL_JOB: Optional[str] = None  # default job label; falls back to APP_NAME
    LOKI_LABEL_ENV: Optional[str] = None  # e.g. dev|staging|prod

    # Role Provider Plugin Configuration
    ROLE_PROVIDER_PLUGIN: str = Field(
        default="default",
        description=(
            "Role provider plugin to use for fetching user roles. "
            "Options: 'default' (parse from JWT claims) or 'accred' (EPFL Accred API)."
            "The 'default' provider expects roles in JWT claims as flat strings like "
            "'co2.user.std@unit:12345'. The 'accred' provider calls the EPFL Accred API"
            "to fetch authorizations and maps them to roles based on accredunitid."
        ),
    )

    # EPFL Accred API Configuration (for 'accred' role provider)
    ACCRED_API_URL: Optional[str] = Field(
        default=None,
        description="EPFL Accred API base URL (e.g., https://api.epfl.ch/v1/accreds)",
    )
    ACCRED_API_USERNAME: Optional[str] = Field(
        default=None,
        description="EPFL Accred API username for Basic Auth",
    )
    ACCRED_API_KEY: Optional[str] = Field(
        default=None,
        description="EPFL Accred API key/password for Basic Auth",
    )
    ACCRED_API_HEALTH_URL: Optional[str] = Field(
        default=None,
        description="EPFL Accred API health check URL",
    )

    # OAuth/OIDC Configuration (supports Keycloak, Entra ID, or other OIDC providers)
    OAUTH_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="OAuth2/OIDC Client ID",
    )
    OAUTH_CLIENT_SECRET: Optional[str] = Field(
        default=None,
        description="OAuth2/OIDC Client Secret",
    )
    OAUTH_ISSUER_URL: Optional[str] = Field(
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
    OAUTH_TENANT_ID: Optional[str] = Field(
        default=None,
        description="OAuth2/OIDC Tenant ID or Realm (if applicable)",
    )
    OAUTH_SCOPE: Optional[str] = Field(
        default="openid profile email",
        description="OAuth2/OIDC scopes to request (space-separated)",
    )
    OAUTH_COOKIE_PATH: Optional[str] = Field(
        default="/",
        description="OAuth2/OIDC cookie path",
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_HOURS: int = 12
    # Frontend URL for redirects
    FRONTEND_URL: str = Field(
        default="http://localhost:9000",
        description="Frontend application URL for OAuth redirects",
    )

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


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
