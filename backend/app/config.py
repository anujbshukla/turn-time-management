from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Turn Time Management API"
    environment: str = "development"
    api_version: str = "1.0.0"

    database_url: str

    sla_minutes: int = Field(default=120, ge=1)
    log_level: str = "INFO"

    allowed_origins: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:5174,"
        "http://127.0.0.1:5174"
    )

    # ---------------------------------------------------------
    # Global Copilot V2 / semantic provider
    # ---------------------------------------------------------

    copilot_nl_v2_enabled: bool = False

    copilot_nl_provider: str = "gemini"

    copilot_nl_model: str = "gemini-2.5-flash-lite"

    copilot_nl_base_url: str = (
        "https://generativelanguage.googleapis.com/v1beta"
    )

    copilot_nl_timeout_seconds: float = Field(
        default=45,
        gt=0,
    )

    copilot_nl_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
    )

    copilot_nl_retry_base_seconds: float = Field(
        default=2,
        ge=0,
    )

    copilot_nl_retry_max_seconds: float = Field(
        default=15,
        ge=0,
    )

    gemini_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()