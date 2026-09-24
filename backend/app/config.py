from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://afm_user:change_me@localhost:5432/afm"
    secret_key: str = "change-this-development-secret"
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173"
    admin_email: str = "admin@afm.local"
    admin_password: str = "change-me-on-first-run"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
