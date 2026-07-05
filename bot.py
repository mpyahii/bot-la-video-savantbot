"""
Telegram bot: pokea link ya video -> download kwa yt-dlp -> tuma faili kwa mtumiaji.

Jinsi ya kutumia:
1. Weka BOT_TOKEN yako (kutoka @BotFather) kwenye environment variable TG_BOT_TOKEN
   au badilisha moja kwa moja kwenye kodi hapa chini (siyo salama kwa production).
2. Sakinisha dependencies:  pip install -r requirements.txt --break-system-packages
3. Hakikisha ffmpeg imesakinishwa kwenye mfumo wako (apt install ffmpeg / brew install ffmpeg)
4. Run:  python bot.py
"""

import os
import re
import glob
import shutil
import logging
import tempfile

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import yt_dlp

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")

# Telegram bot API (isiyo local) ina limit ya ~50MB kwa kutuma faili.
# Ukihitaji faili kubwa zaidi, unahitaji kuendesha "Local Bot API Server" mwenyewe.
MAX_TELEGRAM_SIZE_BYTES = 50 * 1024 * 1024

URL_REGEX = re.compile(r"https?://\S+")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Habari! Nitumie link ya video (YouTube, TikTok, Instagram, n.k) "
        "nami nitakudownloadia na kukurudishia hapa hapa.\n\n"
        "Amri:\n"
        "/start - maelezo haya\n"
        "Tuma link tu ya video kwenye ujumbe wa kawaida."
    )


def download_video(url: str, out_dir: str) -> str:
    """Download video kwa yt-dlp na rudisha njia ya faili lililopakuliwa."""
    ydl_opts = {
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        # Chagua fomati bora isiyozidi ~720p ili kupunguza ukubwa wa faili
        # (unaweza kubadilisha kulingana na mahitaji yako)
        "format": "bv*[height<=720]+ba/b[height<=720]/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    files = glob.glob(os.path.join(out_dir, "*"))
    if not files:
        raise RuntimeError("Hakuna faili lililopakuliwa.")
    # Chukua faili kubwa zaidi (kwa kawaida ndio video baada ya merge)
    return max(files, key=os.path.getsize)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = URL_REGEX.search(text)
    if not match:
        await update.message.reply_text(
            "Sijaona link ya video. Tafadhali tuma link kamili (inayoanza na http/https)."
        )
        return

    url = match.group(0)
    status_msg = await update.message.reply_text("⏳ Ninapakua video, subiri kidogo...")

    tmp_dir = tempfile.mkdtemp(prefix="ytdlp_")
    try:
        filepath = download_video(url, tmp_dir)
        size = os.path.getsize(filepath)

        if size > MAX_TELEGRAM_SIZE_BYTES:
            await status_msg.edit_text(
                "⚠️ Video ni kubwa kuliko limit ya kutuma kwenye Telegram (50MB). "
                "Jaribu link nyingine yenye ubora wa chini, au tumia local Bot API server."
            )
            return

        await status_msg.edit_text("✅ Nimepata video, ninatuma sasa...")
        with open(filepath, "rb") as f:
            await update.message.reply_video(
                video=f,
                caption="Hii hapa video yako 🎬",
                supports_streaming=True,
                read_timeout=120,
                write_timeout=120,
            )
        await status_msg.delete()

    except Exception as e:
        logger.exception("Download error")
        await status_msg.edit_text(f"❌ Kuna hitilafu: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    if BOT_TOKEN == "PUT_YOUR_TOKEN_HERE":
        raise SystemExit(
            "Tafadhali weka TG_BOT_TOKEN yako (environment variable) au badilisha BOT_TOKEN kwenye bot.py"
        )

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot inaanza...")
    app.run_polling()


if __name__ == "__main__":
    main()
