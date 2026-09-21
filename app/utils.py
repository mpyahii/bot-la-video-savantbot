from __future__ import annotations

import re
from urllib.parse import urlsplit


URL_REGEX = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
INVALID_FILENAME_CHARS = re.compile(r"[\\/:*?\"<>|\x00-\x1f]+")


def extract_url(text: str) -> str | None:
    match = URL_REGEX.search(text or "")
    if not match:
        return None
    return match.group(0).rstrip(".,!?;:)")


def validate_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in {"http", "https"}
        and bool(parsed.hostname)
        and not parsed.username
        and not parsed.password
    )


def validate_video_url(url: str) -> tuple[bool, str | None]:
    if not validate_url(url):
        return False, "invalid URL"
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.lower().rstrip("/")
    if hostname in {"www.tiktok.com", "tiktok.com"} and path in {
        "/about",
        "/in/about",
        "/discover",
        "/foryou",
        "/explore",
    }:
        return False, "send a direct TikTok video link, not a TikTok information page"
    return True, None


def domain_for_log(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "unknown").lower()
    except ValueError:
        return "unknown"


def sanitize_filename(title: str, fallback: str = "video", max_length: int = 120) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub(" ", title).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or fallback)[:max_length].rstrip(" .") or fallback