FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

VOLUME ["/data"]

ENV TELEGRAM_RESENDER_WHITELIST_PATH=/data/whitelist.csv
ENV TELEGRAM_RESENDER_STORAGE_PATH=/data/telegram_resender.sqlite3
ENV TELEGRAM_RESENDER_LOG_FORMAT=JSON

CMD ["telegram-resender"]
