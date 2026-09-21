import pytest

import app.config
from app.config import Settings


def test_settings_load_required_and_optional_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TG_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DOWNLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_VIDEO_HEIGHT", "2160")
    settings = Settings.from_env()
    assert settings.bot_token == "test-token"
    assert settings.max_video_height == 2160
    assert settings.bot_api_base_url.endswith("/bot")
    assert settings.bot_api_file_url.endswith("/file/bot")


def test_settings_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    monkeypatch.setattr(app.config, "load_dotenv", lambda: None)
    with pytest.raises(ValueError, match="TG_BOT_TOKEN"):
        Settings.from_env()