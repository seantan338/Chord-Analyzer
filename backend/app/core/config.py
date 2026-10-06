"""Application settings, loaded from environment variables (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ANALYZER_VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"

    # Storage
    data_dir: Path = Path("./data")
    tmp_dir: Path | None = None  # defaults to <data_dir>/tmp

    # Upload / audio limits
    max_upload_mb: int = Field(default=50, ge=1, le=500)
    min_duration_seconds: float = Field(default=5.0, ge=1.0)
    max_duration_seconds: float = Field(default=900.0, ge=10.0)
    temp_file_ttl_minutes: int = Field(default=60, ge=1)

    # Job execution
    job_runner: Literal["process", "inline"] = "process"
    job_timeout_seconds: int = Field(default=300, ge=10)
    max_concurrent_jobs: int = Field(default=2, ge=1, le=16)
    max_queued_jobs: int = Field(default=20, ge=1)

    # Analysis
    chord_vocabulary: Literal["majmin", "extended"] = "extended"

    # HTTP
    cors_origins: str = "http://localhost:3000"
    api_key: str | None = None
    rate_limit_analyze_per_minute: int = Field(default=10, ge=0)
    rate_limit_read_per_minute: int = Field(default=300, ge=0)
    trust_proxy_headers: bool = False

    # External binaries
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    @field_validator("api_key")
    @classmethod
    def _empty_key_is_none(cls, value: str | None) -> str | None:
        return value or None

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def db_path(self) -> Path:
        return self.data_dir / "chord_analyzer.db"

    @property
    def temp_root(self) -> Path:
        return self.tmp_dir or (self.data_dir / "tmp")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
