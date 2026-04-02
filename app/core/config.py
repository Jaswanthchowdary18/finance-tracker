"""
Application configuration — reads from environment or .env file.
All settings are centralized here for easy management.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Project metadata
    PROJECT_NAME: str = "Finance Tracker API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database — SQLite by default; swap DATABASE_URL in .env for PostgreSQL/MySQL
    DATABASE_URL: str = "sqlite:///./finance_tracker.db"

    # JWT Authentication
    SECRET_KEY: str = "super-secret-key-change-in-production-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Pagination defaults
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # CORS — restrict in production
    CORS_ORIGINS: List[str] = ["*"]

    # Environment
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
