import asyncio
import logging
from telegram import Update

from app.bot import DownloadManager, build_application
from app.config import Settings
from app.downloader import VideoDownloader
from app.storage import DownloadStorage


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    settings = Settings.from_env()
    storage = DownloadStorage(settings.download_dir, settings.min_free_disk_mb)
    downloader = VideoDownloader(settings, storage)
    manager = DownloadManager(downloader, storage, settings)
    application = build_application(settings, manager)
    logging.getLogger(__name__).info(
        "action=bot_start api_base=%s download_dir=%s",
        settings.telegram_api_base_url,
        settings.download_dir,
    )
    asyncio.set_event_loop(asyncio.new_event_loop())
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
