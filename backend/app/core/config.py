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
    DB_USER: str = Field(..., description="Database user (REQUIRED)")
    DB_PASSWORD: str = Field(..., description="Database password (REQUIRED)")
    DB_HOST: str = Field(..., description="Database host (REQUIRED)")
    DB_PORT: int = Field(..., description="Database port (REQUIRED)")
    DB_NAME: str = Field(..., description="Database name (REQUIRED)")

    @property
    def DATABASE_URL(self) -> str:
        # return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?async_fallback=True"

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
