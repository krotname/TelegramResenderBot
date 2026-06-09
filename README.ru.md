# Telegram Resender

[![CI](https://github.com/krotname/Bot-Telegram-Resender/actions/workflows/ci.yml/badge.svg)](https://github.com/krotname/Bot-Telegram-Resender/actions/workflows/ci.yml)
[![CodeQL](https://github.com/krotname/Bot-Telegram-Resender/actions/workflows/codeql.yml/badge.svg)](https://github.com/krotname/Bot-Telegram-Resender/actions/workflows/codeql.yml)
[![Scorecard](https://api.scorecard.dev/projects/github.com/krotname/Bot-Telegram-Resender/badge)](https://scorecard.dev/viewer/?uri=github.com/krotname/Bot-Telegram-Resender)
[![codecov](https://codecov.io/gh/krotname/Bot-Telegram-Resender/branch/master/graph/badge.svg)](https://codecov.io/gh/krotname/Bot-Telegram-Resender)
[![PyPI](https://img.shields.io/pypi/pyversions/telegram-resender.svg)](https://pypi.org/project/telegram-resender/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Coverage](https://img.shields.io/badge/coverage-90%2B-green)

[English README](README.en.md)

## Что это

Этот бот проверяет текстовые сообщения пользователей по белому списку и пересылает
разрешенные сообщения в указанный чат/группу.

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
# или одной командой:
python -m pip install -e .[dev]
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
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
pytest
```

## Защита веток

Для `master` (и для `main` после его появления) настроена автоматическая защита ветки с
обязательными check’ами (`lint`, `types`, `tests`, `security`, `CodeQL`) и обязательным ревью.

- [docs/branch-protection.md](docs/branch-protection.md)
- [.github/workflows/branch-protection.yml](.github/workflows/branch-protection.yml)

## Вклад в проект

Смотрите [CONTRIBUTING.md](CONTRIBUTING.md) и [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Безопасность

Смотрите [SECURITY.md](SECURITY.md).
