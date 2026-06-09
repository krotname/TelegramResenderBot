# Telegram Resender

[![CI](https://github.com/krotname/Bot-Telegram-Resender/actions/workflows/ci.yml/badge.svg)](https://github.com/krotname/Bot-Telegram-Resender/actions/workflows/ci.yml)
[![CodeQL](https://github.com/krotname/Bot-Telegram-Resender/actions/workflows/codeql.yml/badge.svg)](https://github.com/krotname/Bot-Telegram-Resender/actions/workflows/codeql.yml)
[![Scorecard](https://api.scorecard.dev/projects/github.com/krotname/Bot-Telegram-Resender/badge)](https://scorecard.dev/viewer/?uri=github.com/krotname/Bot-Telegram-Resender)
[![codecov](https://codecov.io/gh/krotname/Bot-Telegram-Resender/branch/master/graph/badge.svg)](https://codecov.io/gh/krotname/Bot-Telegram-Resender)
[![PyPI](https://img.shields.io/pypi/pyversions/telegram-resender.svg)](https://pypi.org/project/telegram-resender/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[English README](README.en.md)

## Что это

Бот пересылает текстовые сообщения из Telegram в целевой чат только от пользователей,
которые есть в `whitelist`.

## Основной сценарий

- пользователь отправляет текст;
- сообщение валидируется и нормализуется;
- если пользователь в белом списке — формируется предсказуемый текст и пересылается в
  `forward_chat_id`;
- если нет — возвращается сообщение об отказе.

## Быстрый старт

1. Установите Python 3.12+.
2. Создайте `.env` на основе `.env.example`.
3. Установите зависимости через pip:

```bash
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
# или в один шаг:
python -m pip install -e .[dev]
copy .env.example .env      # Windows
# или: cp .env.example .env  # Linux/macOS
python -m telegram_resender
```

## Конфигурация

| Переменная | Обязательна | Описание |
|---|---|---|
| `TELEGRAM_RESENDER_BOT_TOKEN` | да | токен Telegram-бота |
| `TELEGRAM_RESENDER_FORWARD_CHAT_ID` | да | ID чата/группы для пересылки |
| `TELEGRAM_RESENDER_WHITELIST_PATH` | нет | путь к CSV-файлу (по умолчанию `whitelist.csv`) |
| `TELEGRAM_RESENDER_REQUEST_ACCEPTED_MESSAGE` | нет | текст на успешное принятие |
| `TELEGRAM_RESENDER_ACCESS_DENIED_MESSAGE` | нет | текст при отказе |
| `TELEGRAM_RESENDER_LOG_LEVEL` | нет | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` |
| `TELEGRAM_RESENDER_POLLING_TIMEOUT` | нет | timeout для polling, по умолчанию `30` |

## Установка зависимостей и качество

- Основные зависимости: `requirements.txt`
- Зависимости разработки: `requirements-dev.txt`

Ключевые проверки:

- `ruff` (линт/формат)
- `mypy` (строгая типизация)
- `pytest` (unit/integration/conversation/security)
- `CodeQL`, `Codecov`, Dependabot, Scorecard

## Запуск тестов

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
pytest
```

### Категории тестов

- `tests/unit/*` — unit
- `tests/integration/*` — интеграционные
- `tests/conversation/*` — сценарии поведения
- `tests/security/*` — проверки безопасности конфигурации

## Защита веток

Ветка `master` имеет включённую защиту. Для поддержки `main` выполните:

```powershell
pwsh ./scripts/setup-branch-protection.ps1 -Repository krotname/Bot-Telegram-Resender
```

Детали в [docs/branch-protection.md](docs/branch-protection.md).

## Архитектура

- `whitelist.py` — чтение и нормализация белого списка;
- `service.py` — бизнес-правила и решение `ForwardingDecision`;
- `formatting.py` — форматирование пересылаемого текста;
- `app.py` — адаптер Telegram (aiogram) к доменной модели;
- `settings.py` — валидация конфигурации;
- `cli.py` и `__main__.py` — запуск приложения.

## Документация

- [README.ru.md](README.ru.md) — дублированный русский вариант
- [README.en.md](README.en.md) — английская версия
- [Architecture](docs/architecture.md)
- [Testing strategy](docs/testing.md)
