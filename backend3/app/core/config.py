import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend3/app/core/config.py -> raíz del repositorio, donde vive el .env
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS")
    if configured_origins is None:
        configured_origins = dotenv_values(ENV_FILE).get("CORS_ORIGINS", "")
    return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    SUPABASE_URL: str
    SUPABASE_KEY: str
    GOOGLE_API_KEY: str
    SUPABASE_JWT_SECRET: str = ""
    AUTH_ENABLED: bool = True
    GEMINI_AGENT_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_FALLBACK_MODEL: str = "gemini-3.8-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_MAX_RETRIES: int = 2
    CHAT_HISTORY_TURNS: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
