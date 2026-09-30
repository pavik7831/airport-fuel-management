from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            Path(__file__).resolve().parents[1] / ".env",
            Path(__file__).resolve().parents[2] / ".env",
        ),
        extra="ignore",
    )
    database_url: str = "postgresql+asyncpg://afm:afm@localhost:5432/afm"
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = Field(default=30, gt=0)
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    csrf_secret: str = Field(min_length=32)
    frontend_origins: str = "http://localhost:5173"
    default_currency: str = "USD"
    default_quantity_unit: str = "US_GALLON"
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def use_async_postgresql_driver(cls, value: str) -> str:
        url = make_url(value)
        if url.drivername == "postgresql":
            return url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
        return value


settings = Settings()
