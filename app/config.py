from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Freepik + Higgsfield AI FastAPI"
    app_version: str = "1.1.0"

    freepik_api_key: str | None = None
    freepik_base_url: str = Field(
        default="https://api.freepik.com",
        validation_alias=AliasChoices("FREEPIK_BASE_URL", "FREEPIK_API_BASE_URL"),
    )

    higgsfield_base_url: str = Field(default="https://platform.higgsfield.ai")
    higgsfield_api_key: str | None = None
    higgsfield_api_secret: str | None = None
    higgsfield_api_token: str | None = None

    default_timeout_seconds: float = 120.0


@lru_cache
def get_settings() -> Settings:
    return Settings()

