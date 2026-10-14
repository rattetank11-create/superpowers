from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # БД: SQLite по умолчанию, в docker-compose — PostgreSQL.
    database_url: str = "sqlite:///./data/app.db"
    redis_url: str = "redis://localhost:6379/0"
    # rq — фоновые задачи через Redis + RQ-воркер; inline — в процессе API (для разработки/тестов).
    task_mode: str = "rq"
    upload_dir: Path = Path("./data/uploads")

    max_upload_mb: int = 500
    chunk_size_mb: int = 8
    # Незавершённые загрузки старше этого удаляются.
    upload_ttl_minutes: int = 60
    # Лимит новых загрузок с одного IP в час.
    rate_limit_uploads_per_hour: int = 10
    # Доверять X-Forwarded-For (включать только за своим reverse proxy, например Caddy).
    trust_proxy: bool = False
    cors_origins: str = "http://localhost:3000"
    job_timeout_seconds: int = 900

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def chunk_size(self) -> int:
        return self.chunk_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
