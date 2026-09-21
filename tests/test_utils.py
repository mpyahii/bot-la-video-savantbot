from app.utils import (
    domain_for_log,
    extract_url,
    sanitize_filename,
    validate_url,
    validate_video_url,
)


def test_extract_url_trims_sentence_punctuation() -> None:
    assert extract_url("download https://example.com/video?id=1.") == "https://example.com/video?id=1"


def test_validate_url_rejects_local_paths_and_credentials() -> None:
    assert not validate_url("file:///etc/passwd")
    assert not validate_url("https://user:password@example.com/video")
    assert validate_url("https://www.youtube.com/watch?v=abc")


def test_sanitize_filename_removes_path_characters_and_limits_length() -> None:
    value = sanitize_filename("../secret:video?" + "x" * 200)
    assert "/" not in value and ":" not in value and "?" not in value
    assert len(value) <= 120


def test_domain_for_log_is_safe() -> None:
    assert domain_for_log("https://WWW.Example.com/path") == "www.example.com"


def test_tiktok_information_page_is_not_treated_as_video() -> None:
    valid, error = validate_video_url("https://www.tiktok.com/in/about")
    assert not valid
    assert error and "direct TikTok video" in error


def test_tiktok_video_and_short_links_are_accepted() -> None:
    assert validate_video_url("https://www.tiktok.com/@creator/video/123")[0]
    assert validate_video_url("https://vt.tiktok.com/ZSabc123/")[0]