# app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # CROO
    croo_api_url: str = "https://api.croo.network"
    croo_ws_url: str = "wss://api.croo.network/ws"
    croo_sdk_key: str = ""
    internal_api_key: str = ""
    croo_orchestrator_sdk_key: str = ""
    researchmint_service_id: str = ""

    # AI / Search
    groq_api_key: str = ""
    tavily_api_key: str = ""
    news_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./supplymind.db"

    # Cache
    redis_url: str = "redis://localhost:6379"

    # App
    port: int = 8000
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache()
def get_settings() -> Settings:
    return Settings()