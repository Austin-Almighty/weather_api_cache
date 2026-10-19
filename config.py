from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_ignore_empty=True)

    weather_api_key: Annotated[SecretStr, Field(min_length=1)]
    api_base_url: str = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/"
    redis_url: str = "redis://127.0.0.1:6379/0"
    cache_ttl_seconds: Annotated[int, Field(ge=1)] = 43200


@lru_cache
def get_settings() -> Settings:
    return Settings()
