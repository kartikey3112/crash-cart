"""Application settings, read from CRASHCART_* environment variables (or a local .env file)."""

from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dev-only defaults. Production refuses to start if any secret is still one of these.
_DEV_JWT_SECRET = "dev-only-jwt-secret-not-for-production"
_DEV_TEST_TOKEN = "dev-test-token"
_DEV_ADMIN_PASSWORD = "admin-dev-password"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRASHCART_", env_file=".env", extra="ignore")

    environment: str = "dev"  # "dev" or "production"
    database_url: str = "sqlite:///./crashcart.db"

    jwt_secret: str = _DEV_JWT_SECRET
    jwt_expire_minutes: int = 60
    bcrypt_rounds: int = 12

    # Shared secret for /test/reset and for enabling bug switches.
    test_token: str = _DEV_TEST_TOKEN
    # How long the slow_products bug sleeps.
    slow_bug_delay_ms: int = 2000

    admin_email: str = "admin@crashcart.test"
    admin_password: str = _DEV_ADMIN_PASSWORD

    # Comma-separated list of origins allowed to call the API from a browser.
    # Local defaults: Vite dev server (5173) and the production preview UI tests use (4173).
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _no_dev_secrets_in_production(self) -> Self:
        if self.environment == "production":
            insecure = [
                name
                for name, value, default in (
                    ("jwt_secret", self.jwt_secret, _DEV_JWT_SECRET),
                    ("test_token", self.test_token, _DEV_TEST_TOKEN),
                    ("admin_password", self.admin_password, _DEV_ADMIN_PASSWORD),
                )
                if value == default
            ]
            if insecure:
                raise ValueError(f"Refusing to start in production with dev defaults: {insecure}")
            if len(self.jwt_secret) < 32:
                # RFC 7518: an HS256 key should be at least 256 bits.
                raise ValueError("jwt_secret must be at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
