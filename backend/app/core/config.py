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

    # Live session gateway: heartbeat cadence and the stale-disconnect threshold.
    # Threshold starts at a generous 3x the heartbeat interval -- too aggressive
    # flags real connections as dropped; too lenient delays noticing a real drop.
    HEARTBEAT_INTERVAL_SECONDS: int = 10
    STALE_SESSION_THRESHOLD_SECONDS: int = 30

    # Evaluation pipeline: how long a submission may sit unacked in the Redis
    # Streams Pending Entries List (a worker likely crashed before XACK)
    # before the recovery sweep reclaims and redispatches it.
    SUBMISSION_PEL_MIN_IDLE_MS: int = 30_000

    # Results: how often the beat sweep checks for exams past end_time that
    # were never manually closed, so mv_exam_results still gets refreshed.
    EXAM_AUTO_CLOSE_SWEEP_SECONDS: int = 60

    # Security
    SECRET_KEY: str = "super_secret_key_skilltrace_local_dev_12345"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    # bcrypt work factor; tests lower it (4) purely for speed -- keep >= 12 in production.
    BCRYPT_ROUNDS: int = 12

    # Frontend: the JWT is set as an httpOnly cookie on login (not exposed to
    # JS, so an XSS bug can't exfiltrate it) rather than stored in
    # localStorage. The Authorization: Bearer header path stays supported
    # too, for the API/test clients that already use it.
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    ACCESS_TOKEN_COOKIE_NAME: str = "access_token"
    COOKIE_SECURE: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
