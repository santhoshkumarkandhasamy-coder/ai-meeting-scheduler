from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Claude
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    # Voice replies should be fast; raise to "medium"/"high" for harder scheduling logic.
    anthropic_effort: str = "low"

    # Google OAuth (the "Web application" client used by the mobile app's serverAuthCode)
    google_client_id: str = ""
    google_client_secret: str = ""

    # Security
    jwt_secret: str = "change-me"
    jwt_expiry_days: int = 30
    # Fernet key used to encrypt Google refresh tokens at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str = ""

    database_url: str = "sqlite:///./meeting_assistant.db"

    # Reminder scheduler
    scheduler_enabled: bool = True
    reminder_poll_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
