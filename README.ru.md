# Telegram Resender

[![CI](https://github.com/krotname/TelegramResenderBot/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/krotname/TelegramResenderBot/actions/workflows/ci.yml?query=branch%3Amaster)
[![CodeQL](https://github.com/krotname/TelegramResenderBot/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/krotname/TelegramResenderBot/actions/workflows/codeql.yml?query=branch%3Amaster)
[![Scorecard](https://github.com/krotname/TelegramResenderBot/actions/workflows/scorecard.yml/badge.svg?branch=master)](https://github.com/krotname/TelegramResenderBot/actions/workflows/scorecard.yml?query=branch%3Amaster)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776ab)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Coverage Gate](https://img.shields.io/badge/coverage%20gate-90%25%2B-2ea44f)](docs/testing.md)

[English README](README.md)

## Что это

Этот бот проверяет текстовые сообщения пользователей по белому списку и пересылает
разрешенные сообщения в указанный чат/группу.

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
copy .env.example .env      # Windows
# или: cp .env.example .env  # Linux/macOS
python -m telegram_resender
```

## Конфигурация

- `TELEGRAM_RESENDER_BOT_TOKEN` — токен Telegram-бота (обязательный)
- `TELEGRAM_RESENDER_FORWARD_CHAT_ID` — id чата/группы для пересылки
- `TELEGRAM_RESENDER_WHITELIST_PATH` — путь к whitelist.csv (по умолчанию `whitelist.csv`)
- `TELEGRAM_RESENDER_LOG_LEVEL` — уровень логов
- `TELEGRAM_RESENDER_POLLING_TIMEOUT` — таймаут поллинга

Формат whitelist:

```csv
alice
@bob
```

## Тесты и качество

- `tests/unit` — чистые unit-тесты доменной логики
- `tests/integration` — сборка сервиса и контура настроек
- `tests/conversation` — сценарии пользовательского диалога
- `tests/security` — проверки безопасности конфигурации

Запуск:

```bash
pytest
```

## Вклад в проект

Смотрите [CONTRIBUTING.md](CONTRIBUTING.md) и [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Безопасность

Смотрите [SECURITY.md](SECURITY.md).
