"""Application configuration using Pydantic settings."""

from functools import lru_cache

from pydantic import Field
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

    # Database - REQUIRED
    DATABASE_URL: str = Field(
        default="CHANGE_ME_TO_A_VALID_DATABASE_URL",
        description="PostgreSQL database URL (REQUIRED). Example: postgresql+psycopg://user:pass@host:5432/dbname",
    )

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

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
