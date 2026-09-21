from __future__ import annotations

import shutil
import logging
import threading
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageError(RuntimeError):
    pass


class DownloadStorage:
    COMPLETED_MARKER = ".completed"

    def __init__(self, root: Path, min_free_disk_mb: int, retention_seconds: int = 7200) -> None:
        self.root = root
        self.min_free_disk_bytes = min_free_disk_mb * 1024 * 1024
        self.retention_seconds = retention_seconds
        self._active_jobs: set[Path] = set()
        self._active_lock = threading.Lock()

    def ensure_capacity(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        free_bytes = shutil.disk_usage(self.root).free
        if free_bytes < self.min_free_disk_bytes:
            raise StorageError("insufficient disk space")

    def create_job_dir(self, job_id: str | None = None) -> Path:
        self.ensure_capacity()
        prefix = f"{job_id}-" if job_id else ""
        job_dir = self.root / f"{prefix}{uuid.uuid4().hex}"
        job_dir.mkdir(mode=0o700)
        with self._active_lock:
            self._active_jobs.add(job_dir)
        return job_dir

    def mark_completed(self, job_dir: Path) -> None:
        self._ensure_inside_root(job_dir)
        marker = job_dir / self.COMPLETED_MARKER
        marker.touch()
        with self._active_lock:
            self._active_jobs.discard(job_dir)

    def cleanup(self, job_dir: Path) -> None:
        self._ensure_inside_root(job_dir)
        with self._active_lock:
            self._active_jobs.discard(job_dir)
        try:
            shutil.rmtree(job_dir)
        except FileNotFoundError:
            pass
        except (PermissionError, OSError):
            raise StorageError(f"could not remove job directory {job_dir.name}")

    def cleanup_expired(self) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - self.retention_seconds
        with self._active_lock:
            active_jobs = set(self._active_jobs)
        removed = 0
        for entry in self.root.iterdir():
            if not entry.is_dir() or entry in active_jobs:
                continue
            try:
                marker = entry / self.COMPLETED_MARKER
                timestamp = marker.stat().st_mtime if marker.exists() else entry.stat().st_mtime
                if timestamp >= cutoff:
                    continue
                self.cleanup(entry)
                removed += 1
            except (FileNotFoundError, PermissionError, OSError) as exc:
                logger.warning("action=cleanup_failed path=%s error_type=%s", entry.name, type(exc).__name__)
        return removed

    def _ensure_inside_root(self, job_dir: Path) -> None:
        root = self.root.resolve()
        candidate = job_dir.resolve()
        if candidate == root or root not in candidate.parents:
            raise StorageError("job directory is outside configured storage")