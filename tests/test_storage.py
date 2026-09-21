import os
import time

from app.storage import DownloadStorage


def test_storage_creates_unique_private_job_directories(tmp_path) -> None:
    storage = DownloadStorage(tmp_path, min_free_disk_mb=1)
    first = storage.create_job_dir()
    second = storage.create_job_dir()
    assert first != second
    assert first.stat().st_mode & 0o777 == 0o700
    storage.cleanup(first)
    storage.cleanup(second)
    assert not first.exists()
    assert not second.exists()


def test_cleanup_expired_removes_completed_jobs_but_keeps_active_jobs(tmp_path) -> None:
    storage = DownloadStorage(tmp_path, min_free_disk_mb=1, retention_seconds=60)
    expired = storage.create_job_dir("expired")
    storage.mark_completed(expired)
    expired_marker = expired / storage.COMPLETED_MARKER
    old_time = time.time() - 120
    os.utime(expired_marker, (old_time, old_time))

    active = storage.create_job_dir("active")
    active_file = active / "video.mp4"
    active_file.write_bytes(b"in progress")
    os.utime(active, (old_time, old_time))

    assert storage.cleanup_expired() == 1
    assert not expired.exists()
    assert active.exists()
    storage.cleanup(active)