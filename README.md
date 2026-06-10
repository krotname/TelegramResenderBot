# Telegram Resender

[![CI](https://github.com/krotname/TelegramResenderBot/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/krotname/TelegramResenderBot/actions/workflows/ci.yml?query=branch%3Amaster)
[![CodeQL](https://github.com/krotname/TelegramResenderBot/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/krotname/TelegramResenderBot/actions/workflows/codeql.yml?query=branch%3Amaster)
[![Coverage Gate](https://img.shields.io/badge/coverage%20gate-90%25%2B-2ea44f)](docs/testing.md)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/krotname/TelegramResenderBot/badge)](https://securityscorecards.dev/viewer/?uri=github.com/krotname/TelegramResenderBot)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/13150/badge)](https://www.bestpractices.dev/projects/13150)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776ab)](https://www.python.org/downloads/)

![Telegram Resender Bot](docs/assets/project-icon.svg)

[English README](README.en.md)

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
