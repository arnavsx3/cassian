from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    checkpoint_backend: Literal["filesystem", "s3"] = "filesystem"
    checkpoint_dir: Path = Path("data/checkpoints")
    aws_region: str | None = None
    s3_checkpoint_bucket: str | None = None
    s3_checkpoint_prefix: str = "cassian/checkpoints"

    queue_backend: Literal["memory", "sqs"] = "memory"
    sqs_queue_url: str | None = None
    sqs_visibility_timeout: int = 120
    sqs_wait_time_seconds: int = 5

    worker_chunk_delay_seconds: float = 0.05
    embedded_worker_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
