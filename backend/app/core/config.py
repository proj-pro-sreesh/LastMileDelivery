import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Last-Mile Delivery Tracker"
    environment: str = "development"
    database_url: str = "postgresql+psycopg:///lastmile_delivery"
    test_database_url: str = "postgresql+psycopg:///lastmile_delivery_test"
    cors_origins: str = "http://localhost:3000"
    secret_key: str = ""
    access_token_expire_minutes: int = 60 * 24
    notifications_mode: str = "mock"  # "mock" writes in-app rows and logs email/SMS; "disabled" turns off
    # Outbound channel providers (used only when notifications are enabled).
    email_provider: str = "mock"  # "mock" | "resend"
    email_api_key: str = ""
    email_from: str = ""
    sms_provider: str = "mock"  # "mock" | "twilio"
    sms_api_key: str = ""  # twilio format: "AccountSid:AuthToken"
    sms_from: str = ""

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        # Hosted providers (e.g. Render) hand out postgres:// or postgresql:// URLs;
        # SQLAlchemy needs the psycopg driver spelled out.
        if self.database_url.startswith(("postgres://", "postgresql://")):
            self.database_url = self.database_url.replace("postgres://", "postgresql+psycopg://", 1).replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
            if "sslmode=" not in self.database_url:
                separator = "&" if "?" in self.database_url else "?"
                self.database_url += f"{separator}sslmode=require"
        return self

    @model_validator(mode="after")
    def _ensure_secret_key(self) -> "Settings":
        if not self.secret_key:
            if self.environment == "production":
                raise ValueError("SECRET_KEY must be set when ENVIRONMENT=production")
            self.secret_key = secrets.token_hex(32)
        return self

    @property
    def notifications_enabled(self) -> bool:
        return self.notifications_mode.lower() != "disabled"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
