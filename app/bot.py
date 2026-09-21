from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import Settings
from app.downloader import DownloadError, VideoDownloader
from app.storage import DownloadStorage, StorageError
from app.utils import domain_for_log, extract_url, validate_video_url

logger = logging.getLogger(__name__)


class DownloadManager:
    def __init__(self, downloader: VideoDownloader, storage: DownloadStorage, settings: Settings):
        self.downloader = downloader
        self.storage = storage
        self.settings = settings
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_downloads)
        self._state_lock = asyncio.Lock()
        self._active = 0
        self._queued = 0

    async def run(self, url: str, job_id: str) -> Path:
        async with self._state_lock:
            if self._active + self._queued >= self.settings.max_concurrent_downloads + self.settings.max_queued_downloads:
                raise DownloadError("download queue is full")
            self._queued += 1

        async with self.semaphore:
            async with self._state_lock:
                self._queued -= 1
                self._active += 1
            try:
                logger.info("job=%s action=download_started domain=%s", job_id, domain_for_log(url))
                _, filepath = await asyncio.wait_for(
                    asyncio.to_thread(self.downloader.download, url, job_id),
                    timeout=self.settings.download_timeout_seconds,
                )
                return filepath
            finally:
                async with self._state_lock:
                    self._active -= 1


async def cleanup_loop(application: Application) -> None:
    storage: DownloadStorage = application.bot_data["storage"]
    settings: Settings = application.bot_data["settings"]
    while True:
        try:
            removed = await asyncio.to_thread(storage.cleanup_expired)
            if removed:
                logger.info("action=cleanup_finished removed=%s", removed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("action=cleanup_failed")
        await asyncio.sleep(settings.cleanup_interval_seconds)


async def start_background_tasks(application: Application) -> None:
    application.bot_data["cleanup_task"] = asyncio.create_task(cleanup_loop(application))


async def stop_background_tasks(application: Application) -> None:
    task = application.bot_data.pop("cleanup_task", None)
    if task:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def build_application(settings: Settings, manager: DownloadManager) -> Application:
    builder: ApplicationBuilder = Application.builder().token(settings.bot_token)
    builder = builder.base_url(settings.bot_api_base_url).base_file_url(settings.bot_api_file_url)
    builder = builder.post_init(start_background_tasks).post_shutdown(stop_background_tasks)
    application = builder.build()
    application.bot_data["manager"] = manager
    application.bot_data["storage"] = manager.storage
    application.bot_data["settings"] = settings
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    return application


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Habari! Tuma link ya video, nami nitapakua na kukutumia.\n\n"
            "Tumia /help kwa maelekezo."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "1. Tuma URL ya video.\n"
            "2. Subiri download na processing ikamilike.\n"
            "3. Bot itakutumia video.\n\n"
            "Amri: /start, /help, /status"
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    manager: DownloadManager = context.application.bot_data["manager"]
    if update.message:
        await update.message.reply_text(
            f"Downloads zinazoendelea: {manager._active}; zilizopangwa: {manager._queued}"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    url = extract_url(update.message.text)
    valid, validation_error = validate_video_url(url or "")
    if not url or not valid:
        if validation_error and "TikTok" in validation_error:
            await update.message.reply_text(f"❌ {validation_error}.")
            return
        await update.message.reply_text("Tafadhali tuma URL halali inayoanza na http:// au https://.")
        return

    job_id = uuid.uuid4().hex[:12]
    user_id = update.effective_user.id if update.effective_user else "unknown"
    logger.info("job=%s user=%s action=request_received domain=%s", job_id, user_id, domain_for_log(url))
    status_message = await update.message.reply_text("⏳ Preparing your download...")
    manager: DownloadManager = context.application.bot_data["manager"]
    storage: DownloadStorage = context.application.bot_data["storage"]
    settings: Settings = context.application.bot_data["settings"]
    job_dir: Path | None = None
    completed = False
    try:
        await status_message.edit_text("⬇️ Downloading...")
        filepath = await manager.run(url, job_id)
        job_dir = filepath.parent
        await status_message.edit_text("⚙️ Processing video...")
        await status_message.edit_text("📤 Uploading...")
        with filepath.open("rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption="Hii hapa video yako 🎬",
                supports_streaming=True,
                read_timeout=settings.telegram_read_timeout,
                write_timeout=settings.telegram_write_timeout,
                connect_timeout=settings.telegram_connect_timeout,
                pool_timeout=settings.telegram_pool_timeout,
            )
        storage.mark_completed(job_dir)
        completed = True
        await status_message.edit_text("✅ Done.")
        logger.info("job=%s user=%s action=upload_finished", job_id, user_id)
    except DownloadError as exc:
        logger.warning("job=%s user=%s action=download_failed error=%s", job_id, user_id, exc)
        await status_message.edit_text(f"❌ Unable to download this video: {exc}.")
    except StorageError:
        logger.error("job=%s user=%s action=storage_failed", job_id, user_id)
        await status_message.edit_text("❌ Insufficient disk space for this download.")
    except asyncio.TimeoutError:
        logger.error("job=%s user=%s action=download_timeout", job_id, user_id)
        await status_message.edit_text("❌ The download timed out. Please try again later.")
    except TelegramError:
        logger.exception("job=%s user=%s action=upload_failed", job_id, user_id)
        try:
            await status_message.edit_text("❌ Telegram could not receive this video.")
        except TelegramError:
            pass
    except Exception:
        logger.exception("job=%s user=%s action=unexpected_failure", job_id, user_id)
        await status_message.edit_text("❌ Something went wrong while processing this video.")
    finally:
        if job_dir and not completed:
            try:
                storage.cleanup(job_dir)
            except StorageError:
                logger.exception("job=%s action=failed_job_cleanup", job_id)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("telegram_update_error error_type=%s", type(context.error).__name__, exc_info=context.error)