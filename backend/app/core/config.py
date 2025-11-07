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
    API_V1_PREFIX: str = "/api/v1"

    # Database Configuration
    # Option 1: Provide full DATABASE_URL directly (takes precedence)
    DATABASE_URL: Optional[str] = Field(
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

    # necessary to build the DB URL if DATABASE_URL is not provided
    DB_HOST: Optional[str] = Field(
        default=None, description="Database host (optional, for PostgreSQL)"
    )
    DB_PORT: Optional[int] = Field(
        default=None, description="Database port (optional, for PostgreSQL)"
    )

    @computed_field
    def database_url(self) -> str:
        """
        Get the database URL.

        Priority:
        1. If DATABASE_URL is explicitly set, use it
        2. If DB_USER, DB_PASSWORD, DB_HOST, DB_NAME are all set, build PostgreSQL URL
        3. Otherwise, default to SQLite
        """
        # If DATABASE_URL is explicitly provided, use it
        if self.DATABASE_URL:
            return self.DATABASE_URL

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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # OPA Configuration
    OPA_URL: str = "http://localhost:8181"
    OPA_TIMEOUT: float = 1.0
    OPA_ENABLED: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"

    # Loki (optional)
    LOKI_ENABLED: bool = False
    LOKI_URL: Optional[str] = None  # e.g. http://loki:3100
    LOKI_TENANT_ID: Optional[str] = None  # X-Scope-OrgID if multi-tenant
    LOKI_TIMEOUT: float = 2.0  # seconds
    LOKI_LABEL_JOB: Optional[str] = None  # default job label; falls back to APP_NAME
    LOKI_LABEL_ENV: Optional[str] = None  # e.g. dev|staging|prod

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
