FROM python:3.12-slim@sha256:d764629ce0ddd8c71fd371e9901efb324a95789d2315a47db7e4d27e78f1b0e9

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

COPY requirements-bootstrap.lock requirements.lock pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --no-cache-dir --require-hashes -r requirements-bootstrap.lock \
    && python -m pip install --no-cache-dir --require-hashes -r requirements.lock

RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

VOLUME ["/data"]

ENV TELEGRAM_RESENDER_WHITELIST_PATH=/data/whitelist.csv
ENV TELEGRAM_RESENDER_STORAGE_PATH=/data/telegram_resender.sqlite3
ENV TELEGRAM_RESENDER_LOG_FORMAT=JSON

CMD ["python", "-m", "telegram_resender"]
