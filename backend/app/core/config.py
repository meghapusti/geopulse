"""
Central configuration — reads from environment / .env file.
All settings are typed and validated by Pydantic.
"""
from functools import lru_cache
from typing import List, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_ENV: Literal["development", "production", "test"] = "development"
    APP_SECRET_KEY: str = "change-me"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://geopulse:password@localhost:5432/geopulse"
    DATABASE_URL_SYNC: str = "postgresql://geopulse:password@localhost:5432/geopulse"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # NLP
    NLP_INFERENCE_MODE: Literal["onnx", "hf"] = "onnx"
    MODEL_CACHE_DIR: str = "../data/models"
    NLP_BATCH_SIZE: int = 32

    # Data sources
    NEWSAPI_KEY: str = ""
    FRED_API_KEY: str = ""

    # Alerts
    RESEND_API_KEY: str = ""
    ALERT_FROM_EMAIL: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # Ingestion
    INGEST_INTERVAL_MINUTES: int = 15

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
