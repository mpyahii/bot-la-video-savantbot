FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates gosu \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin bot

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY bot.py .
COPY docker-entrypoint.sh .

RUN chmod 755 /app/docker-entrypoint.sh \
    && mkdir -p /tmp/bot-downloads /data/downloads \
    && chown -R bot:bot /app /tmp/bot-downloads /data/downloads

ENTRYPOINT ["/app/docker-entrypoint.sh"]

CMD ["python", "bot.py"]