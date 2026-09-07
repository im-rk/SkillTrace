"""
Application configuration using pydantic-settings.
Includes DB, REDIS_URL, CELERY_BROKER_URL, and other env vars.
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "SkillTrace Exam Platform"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:15432/skilltrace"
    SYNC_DATABASE_URL: str = "postgresql+psycopg://user:password@localhost:15432/skilltrace"
    
    # Redis & Celery
    REDIS_URL: str = "redis://localhost:16379/0"
    CELERY_BROKER_URL: str = "redis://localhost:16379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:16379/2"
    EXAM_START_LOCK_TTL_MS: int = 5000
    
    # Security
    SECRET_KEY: str = "super_secret_key_skilltrace_local_dev_12345"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
