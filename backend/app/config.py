from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
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


settings = Settings()
