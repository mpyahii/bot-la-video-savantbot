from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return parsed


@dataclass(frozen=True)
class Settings:
    bot_token: str
    telegram_api_base_url: str
    telegram_api_id: str | None
    telegram_api_hash: str | None
    max_video_height: int
    max_concurrent_downloads: int
    max_queued_downloads: int
    download_dir: Path
    min_free_disk_mb: int
    download_retention_seconds: int
    cleanup_interval_seconds: int
    download_timeout_seconds: int
    telegram_read_timeout: float
    telegram_write_timeout: float
    telegram_connect_timeout: float
    telegram_pool_timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        bot_token = os.getenv("TG_BOT_TOKEN", "").strip()
        if not bot_token:
            raise ValueError("TG_BOT_TOKEN is required")

        return cls(
            bot_token=bot_token,
            telegram_api_base_url=os.getenv(
                "TELEGRAM_API_BASE_URL", "https://api.telegram.org"
            ).rstrip("/"),
            telegram_api_id=os.getenv("TELEGRAM_API_ID") or None,
            telegram_api_hash=os.getenv("TELEGRAM_API_HASH") or None,
            max_video_height=_int_env("MAX_VIDEO_HEIGHT", 1080),
            max_concurrent_downloads=_int_env("MAX_CONCURRENT_DOWNLOADS", 2),
            max_queued_downloads=_int_env("MAX_QUEUED_DOWNLOADS", 8),
            download_dir=Path(os.getenv("DOWNLOAD_DIR", "/tmp/bot-downloads")),
            min_free_disk_mb=(
                _int_env("MIN_FREE_DISK_GB", 5) * 1024
                if os.getenv("MIN_FREE_DISK_GB")
                else _int_env("MIN_FREE_DISK_MB", 1024)
            ),
            download_retention_seconds=_int_env("DOWNLOAD_RETENTION_HOURS", 2) * 3600,
            cleanup_interval_seconds=_int_env("CLEANUP_INTERVAL_SECONDS", 600),
            download_timeout_seconds=_int_env("DOWNLOAD_TIMEOUT_SECONDS", 1800),
            telegram_read_timeout=float(os.getenv("TELEGRAM_READ_TIMEOUT", "120")),
            telegram_write_timeout=float(os.getenv("TELEGRAM_WRITE_TIMEOUT", "120")),
            telegram_connect_timeout=float(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "30")),
            telegram_pool_timeout=float(os.getenv("TELEGRAM_POOL_TIMEOUT", "30")),
        )

    @property
    def bot_api_base_url(self) -> str:
        return f"{self.telegram_api_base_url}/bot"

    @property
    def bot_api_file_url(self) -> str:
        return f"{self.telegram_api_base_url}/file/bot"