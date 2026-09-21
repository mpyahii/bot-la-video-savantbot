FROM python:3.12-slim

ARG NODE_VERSION=24.6.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/opt/node/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates gosu wget xz-utils \
    && wget -q "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -O /tmp/node.tar.xz \
    && mkdir -p /opt \
    && tar -xJf /tmp/node.tar.xz -C /opt \
    && mv "/opt/node-v${NODE_VERSION}-linux-x64" /opt/node \
    && rm /tmp/node.tar.xz \
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