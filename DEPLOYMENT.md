# VPS Deployment

This project supports two deployment modes:

- Codespaces: the bot talks to `https://api.telegram.org`.
- VPS: Docker runs the bot and a Telegram Local Bot API Server on one private
  Compose bridge network without publishing the API port.

## 1. Install Docker

Install Docker Engine and the Compose plugin using the official instructions
for the Ubuntu release on the VPS. Confirm both commands work:

```bash
docker --version
docker compose version
```

## 2. Get the project and secrets

```bash
git clone <your-repository-url>
cd bot-la-video-savantbot
cp .env.example .env
```

Create an application at <https://my.telegram.org/apps> and set these values
in `.env`:

```env
TG_BOT_TOKEN=your_botfather_token
TELEGRAM_API_ID=your_numeric_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_API_BASE_URL=http://telegram-bot-api:8081
```

Do not commit `.env`. No VPS IP or host port is hardcoded; the bot reaches the
Local API through its private Compose service name.

## One-time Local Bot API initialization

Telegram requires the bot to be logged out from the cloud Bot API before the
same bot token is used with a Local Bot API Server. Stop any running bot first,
then call the cloud API once, replacing the placeholder locally in your shell:

```bash
read -rsp 'Bot token: ' BOT_TOKEN; echo
curl -sS -X POST "https://api.telegram.org/bot${BOT_TOKEN}/logOut"
unset BOT_TOKEN
```

Confirm the response contains `"ok":true`, then start the Compose stack. Do
not put the token directly into shell history or commit it to a file. If you
switch back to the cloud API later, stop the Local Bot API stack and repeat the
same logout step before starting direct cloud polling.

## 3. Start the services

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f bot
```

Use the default `docker-compose.yml` on the VPS. Do not use
`docker-compose.codespaces.yml` there: it is only a workaround for Codespace
Docker daemons with broken bridge-network DNS and uses host networking.

The bot container runs as a non-root user, and `restart: unless-stopped` brings
both services back after a process or host restart. Downloads and Local Bot API
data are stored in named Docker volumes.

The Compose file overrides the API URL for the bot container to the private
service name. Port `8081` is not published to the VPS host, so existing Nginx,
Apache, websites, databases, and other services are not displaced. The bot
waits for the Local API healthcheck before starting.

## 4. Verify operation

Send `/start`, then a small public video URL. Watch the logs for the job ID and
the download/upload phases. Test a larger file only after confirming that the
deployed Local Bot API version supports its size.

## 5. Storage and maintenance

Set `MIN_FREE_DISK_GB` in `.env` to reserve space for the operating system.
Failed jobs are deleted immediately. Successful jobs are retained for two hours
and removed by the bot's cleanup task, which scans every ten minutes by default.
Persistent Local Bot API data can grow, so monitor the Docker volume and host disk:

```bash
docker system df
df -h
```

## 6. Local Bot API notes

The included Compose service uses `aiogram/telegram-bot-api` with `--local` and
passes `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`. Review that image's current
documentation before production rollout because image tags, flags, and Telegram
limits can change. Do not expose port `8081` publicly unless your deployment
specifically requires it. The Compose network is isolated to this project.

Telegram upload capacity is separate from yt-dlp download capacity. The bot can
download large files to disk, but the final send remains constrained by the
Telegram cloud or Local Bot API implementation, available VPS resources, and
current Telegram specifications.