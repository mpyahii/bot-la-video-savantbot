from __future__ import annotations

import glob
import logging
import os
import re
from pathlib import Path

import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget

from app.config import Settings
from app.storage import DownloadStorage

logger = logging.getLogger(__name__)


class DownloadError(RuntimeError):
    pass


class VideoDownloader:
    def __init__(self, settings: Settings, storage: DownloadStorage) -> None:
        self.settings = settings
        self.storage = storage

    def download(self, url: str, job_id: str) -> tuple[Path, Path]:
        job_dir = self.storage.create_job_dir(job_id)
        output_template = str(job_dir / "%(title).120s.%(ext)s")
        options = {
            "outtmpl": output_template,
            "format": (
                f"bv*[height<={self.settings.max_video_height}]+ba/"
                f"b[height<={self.settings.max_video_height}]/b"
            ),
            "merge_output_format": "mp4",
            "noplaylist": True,
            "restrictfilenames": True,
            "windowsfilenames": True,
            "quiet": True,
            "no_warnings": True,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
            "socket_timeout": 30,
            "retries": 3,
            "fragment_retries": 3,
            "js_runtimes": {"node": {}},
            "remote_components": {"ejs": "github"},
            "impersonate": ImpersonateTarget("chrome"),
            "progress_hooks": [self._progress_hook(job_id)],
        }
        if self.settings.cookies_file:
            options["cookiefile"] = str(self.settings.cookies_file)
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([url])
        except Exception as exc:
            logger.warning(
                "job=%s action=yt_dlp_failed error_type=%s error=%s",
                job_id,
                type(exc).__name__,
                self._safe_log_error(str(exc)),
            )
            try:
                self.storage.cleanup(job_dir)
            except Exception:
                logger.exception("job=%s action=failed_download_cleanup", job_id)
            raise DownloadError(self._friendly_error(str(exc))) from exc

        candidates = [
            Path(path)
            for path in glob.glob(str(job_dir / "*") )
            if Path(path).is_file() and not Path(path).name.endswith((".part", ".ytdl"))
        ]
        if not candidates:
            self.storage.cleanup(job_dir)
            raise DownloadError("no media file was produced")
        filepath = max(candidates, key=os.path.getsize)
        return job_dir, filepath

    @staticmethod
    def _progress_hook(job_id: str):
        def hook(data: dict) -> None:
            if data.get("status") == "finished":
                logger.info("job=%s action=download_file_finished", job_id)

        return hook

    @staticmethod
    def _friendly_error(message: str) -> str:
        lowered = message.lower()
        if "sign in to confirm" in lowered or "not a bot" in lowered:
            return "YouTube requires a supported JavaScript runtime or authenticated cookies"
        if "cookies" in lowered or "log in" in lowered or "login required" in lowered:
            return "this video requires login cookies"
        if "private" in lowered or "authentication" in lowered:
            return "private or authentication-required video"
        if "geo" in lowered or "not available in your country" in lowered:
            return "video is unavailable in this region"
        if "unsupported url" in lowered:
            return "unsupported or non-video URL; send a direct public video link"
        if "ffmpeg" in lowered:
            return "FFmpeg could not process this video"
        return "video download failed"

    @staticmethod
    def _safe_log_error(message: str) -> str:
        # yt-dlp errors can echo URLs; avoid logging query strings or credentials.
        detail = (message.splitlines()[-1] if message.splitlines() else "unknown yt-dlp error")[:300]
        return re.sub(r"https?://\S+", "<url>", detail)