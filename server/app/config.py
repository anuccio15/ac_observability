"""Environment-backed application configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AC_",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://ac_metrics:ac_metrics@localhost:5432/ac_metrics"
    edge_api_token: SecretStr = Field(min_length=32)
    log_level: str = "INFO"
    max_compressed_batch_bytes: int = 64 * 1024 * 1024
    max_expanded_batch_bytes: int = 256 * 1024 * 1024
    max_batch_samples: int = 20_000

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("AC_DATABASE_URL must be a PostgreSQL URL")
        return value

    @field_validator("max_compressed_batch_bytes", "max_expanded_batch_bytes", "max_batch_samples")
    @classmethod
    def require_positive_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("batch limits must be positive")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
