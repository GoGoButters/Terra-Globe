from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://terraglobe:changeme_dev_password_123@db:5432/terraglobe"

    # Redis
    redis_url: str = "redis://:changeme_redis_password@redis:6379/0"

    # Auth
    secret_key: str = "changeme_generate_a_long_random_secret_key_here"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:80/api/auth/google/callback"

    # Cesium
    cesium_ion_token: str = ""

    # Frontend
    frontend_url: str = "http://localhost:80"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
