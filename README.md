# Telegram Video Downloader Bot

An asynchronous Telegram bot that accepts a URL supported by yt-dlp, downloads
the best practical MP4-compatible media through FFmpeg, and sends it back to
the user. Each request gets isolated temporary storage and downloads are bounded
to protect the host.

## Architecture

```text
Telegram -> python-telegram-bot -> URL validation -> bounded job manager
			-> yt-dlp + FFmpeg -> per-job filesystem -> Telegram Bot API
```

`bot.py` is the entry point. The `app/` package separates configuration,
handlers, downloading, storage, and URL utilities. yt-dlp supports YouTube,
TikTok, Instagram, Facebook, X/Twitter, Reddit, and other supported sites
without a hardcoded platform allowlist.

## Development in Codespaces

1. Copy `.env.example` to `.env`.
2. Set `TG_BOT_TOKEN` from BotFather. Leave `TELEGRAM_API_BASE_URL` as
	`https://api.telegram.org`.
3. Install FFmpeg and Python dependencies:

	```bash
	sudo apt-get update && sudo apt-get install -y ffmpeg
	python -m pip install -r requirements-dev.txt
	```

4. Run checks and start the bot:

	```bash
	pytest -q
	python bot.py
	```

The normal cloud Bot API has Telegram-enforced upload limits. This project does
not reject downloads based on an artificial 50 MB threshold, but the cloud API
may still reject a file that is too large.

## Configuration

See `.env.example` for every supported variable. The important values are:

| Variable | Purpose |
| --- | --- |
| `TG_BOT_TOKEN` | BotFather token; required and never committed |
| `TELEGRAM_API_BASE_URL` | Cloud API or Local Bot API base URL |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | Credentials used by the Local Bot API server |
| `MAX_VIDEO_HEIGHT` | Quality ceiling, default `1080`; supports `720`, `1440`, `2160`, etc. |
| `MAX_CONCURRENT_DOWNLOADS` | Active yt-dlp jobs, default `2` |
| `MAX_QUEUED_DOWNLOADS` | Waiting jobs before new requests are rejected |
| `DOWNLOAD_DIR` | Filesystem root for isolated job directories |
| `DOWNLOAD_RETENTION_HOURS` | Successful job retention, default `2` |
| `CLEANUP_INTERVAL_SECONDS` | Expiry scan interval, default `600` |
| `MIN_FREE_DISK_GB` | Refuse new jobs below this free-space reserve |
| `COOKIES_FILE` | Optional mounted Netscape cookies file for authenticated sources |

`TELEGRAM_API_BASE_URL` should be the service root. Direct development uses
`https://api.telegram.org`; the integrated Compose stack uses
`http://telegram-bot-api:8081` on its private Compose network. The application
derives the `/bot` and `/file/bot` endpoints required by python-telegram-bot.

## Docker and Local Bot API

The Compose file includes a bot and a Local Bot API Server. The Local Bot API
image needs Telegram API ID and hash values from
<https://my.telegram.org/apps>. Set those, plus `TG_BOT_TOKEN`, in `.env`, then
run:

```bash
docker compose build
docker compose up -d
docker compose logs -f bot
```

The bot and Local Bot API remain separate Compose services on a project-scoped
private bridge network. Port `8081` is not published on the VPS host, so this
stack does not claim or interfere with ports used by other websites. The Local
Bot API server must be
configured according to the image's current official documentation; its actual
maximum upload size and behavior can change.

If the GitHub Codespace Docker daemon cannot provide outbound DNS from bridge
networks, use the development-only override:

```bash
docker compose -f docker-compose.yml -f docker-compose.codespaces.yml up -d --build
```

That override uses host networking only inside the Codespace environment. The
default Compose file remains the isolated VPS configuration and does not claim
host ports.

Before the first Local Bot API run, stop any cloud-polling bot and log the bot
out from the cloud API once:

```bash
read -rsp 'Bot token: ' BOT_TOKEN; echo
curl -sS -X POST "https://api.telegram.org/bot${BOT_TOKEN}/logOut"
unset BOT_TOKEN
```

Proceed only after the response reports `"ok":true`. This one-time migration
step prevents the cloud and Local Bot API servers from competing for updates.

The integrated Compose stack always routes the bot through the Local Bot API.
For direct Codespace development with the cloud API, run `python bot.py` with
`TELEGRAM_API_BASE_URL=https://api.telegram.org`.

## VPS deployment

1. Install Docker and the Compose plugin on Ubuntu.
2. Clone this repository and enter it.
3. Copy `.env.example` to `.env`.
4. Set `TG_BOT_TOKEN`, `TELEGRAM_API_ID`, and `TELEGRAM_API_HASH`.
5. Keep `TELEGRAM_API_BASE_URL=http://telegram-bot-api:8081` when using the
	included Compose network.
6. Review the persistent Docker volumes and set `MIN_FREE_DISK_MB` to leave a
	useful reserve on the VPS.
7. Start with `docker compose up -d --build`.
8. Follow `docker compose logs -f bot` and send `/start` to the bot.
9. Test a file larger than the cloud limit only after confirming the Local Bot
	API deployment supports the desired size.
10. Keep the host firewall closed for the internal API port; only expose public
	 ports required by your own deployment and reverse proxy.

Compose uses `restart: unless-stopped`, isolated persistent volumes, FFmpeg,
and a non-root bot container. Failed jobs are removed immediately. Successful
uploads receive a completion marker and are automatically removed after two
hours by the bot's independent cleanup task; active jobs are never removed by
that scan.

## Commands

- `/start` and `/help`: usage instructions
- `/status`: active and queued download counts

## Limitations and troubleshooting

Download capacity is not Telegram upload capacity. “Unlimited” is not literal:
practical limits depend on VPS disk, RAM, CPU, bandwidth, source availability,
FFmpeg, and Telegram or Local Bot API specifications. Large files are streamed
from disk through a file handle rather than loaded into RAM.

For failures, inspect container logs. The bot returns safe user-facing errors
while logs include job ID, user ID, domain, operation, and exception type; it
does not log tokens, API hashes, cookies, or passwords. Private, geo-restricted,
authentication-required, unsupported, and FFmpeg failures require a different
source URL or authentication. If YouTube reports `Sign in to confirm you are
not a bot`, export a Netscape-format cookies file to `cookies/youtube.txt`, set
`COOKIES_FILE=/run/cookies/youtube.txt` in `.env`, and recreate the bot. Never
commit cookies.