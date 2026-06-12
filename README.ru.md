# Telegram Resender

[![CI](https://github.com/krotname/TelegramResenderBot/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/krotname/TelegramResenderBot/actions/workflows/ci.yml?query=branch%3Amaster)
[![CodeQL](https://github.com/krotname/TelegramResenderBot/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/krotname/TelegramResenderBot/actions/workflows/codeql.yml?query=branch%3Amaster)
[![Coverage Gate](https://img.shields.io/badge/coverage%20gate-70%25%2B-2ea44f)](docs/testing.md)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/krotname/TelegramResenderBot/badge)](https://securityscorecards.dev/viewer/?uri=github.com/krotname/TelegramResenderBot)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776ab)](https://www.python.org/downloads/)

[English README](README.en.md)

## Что это

Этот бот проверяет текстовые сообщения пользователей по белому списку и пересылает
разрешенные сообщения в указанный чат/группу.

Начиная с `1.1.0`, бот по умолчанию говорит по-русски, показывает шаблон заявки,
различает причины отказа и имеет диагностический режим без запуска Telegram polling.

## Возможности

- `/start`, `/help`, `/template`, `/avto` для пользовательского сценария.
- Белый список Telegram username из CSV.
- Понятный отказ для неизвестного пользователя и отдельный отказ для пользователя
  без Telegram username.
- Защита от случайной пересылки коротких приветствий вместо заявки.
- Ответ на неподдерживаемые типы сообщений: фото, документы, стикеры, голосовые.
- Диагностика конфигурации через `telegram-resender doctor`.
- Проверка обязательных полей заявки и опциональное подтверждение перед пересылкой.
- Админские команды для статуса и перезагрузки whitelist без рестарта.
- Детерминированный формат пересылки с request id и временем заявки.

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
copy .env.example .env      # Windows
# или: cp .env.example .env  # Linux/macOS
telegram-resender doctor
telegram-resender
```

Если `doctor` сообщает об ошибке, заполните `.env` до запуска polling.

## Конфигурация

| Переменная | Обязательная | Описание |
|---|---:|---|
| `TELEGRAM_RESENDER_BOT_TOKEN` | да | токен Telegram-бота |
| `TELEGRAM_RESENDER_FORWARD_CHAT_ID` | да | id чата/группы для пересылки |
| `TELEGRAM_RESENDER_WHITELIST_PATH` | нет | путь к whitelist.csv, по умолчанию `whitelist.csv` |
| `TELEGRAM_RESENDER_LOCALE` | нет | `ru` или `en`, по умолчанию `ru` |
| `TELEGRAM_RESENDER_CONFIRM_BEFORE_FORWARD` | нет | `true`, чтобы показывать preview и ждать `/confirm` |
| `TELEGRAM_RESENDER_ADMIN_IDS` | нет | Telegram user id администраторов через запятую |
| `TELEGRAM_RESENDER_LOG_LEVEL` | нет | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `TELEGRAM_RESENDER_POLLING_TIMEOUT` | нет | таймаут polling, по умолчанию `30` |
| `TELEGRAM_RESENDER_REQUEST_ACCEPTED_MESSAGE` | нет | переопределение текста успешной заявки |
| `TELEGRAM_RESENDER_ACCESS_DENIED_MESSAGE` | нет | переопределение текста отказа неизвестному пользователю |

Формат whitelist:

```csv
alice
@bob
```

## Формат заявки

Пользователь может вызвать `/template` или `/avto` и отправить текст:

```text
Объект/здание: Башня А
Дата и время прибытия: 12.06.2026 10:30
Автомобиль: Ford Focus
Госномер: А123ВС
Комментарий: встреча с отделом эксплуатации
```

Пока бот принимает только текст. Медиа и документы не пересылаются.

Обязательные поля: объект/здание, дата и время прибытия, автомобиль, госномер.
Если включить `TELEGRAM_RESENDER_CONFIRM_BEFORE_FORWARD=true`, бот покажет preview
заявки и отправит ее администратору только после `/confirm`. Команда `/cancel`
отменяет ожидающую подтверждения заявку.

## Администрирование

- `/whoami` показывает Telegram user id и chat id. Команда доступна всем, чтобы
  администратор мог узнать свой id для `.env`.
- `/admin_status` показывает версию, locale, целевой чат, размер whitelist,
  число администраторов и режим подтверждения.
- `/whitelist_count` показывает текущий размер whitelist.
- `/reload_whitelist` перечитывает CSV whitelist без рестарта процесса.

Все команды кроме `/whoami` доступны только id из `TELEGRAM_RESENDER_ADMIN_IDS`.

## Тесты и качество

- `tests/unit` — чистые unit-тесты доменной логики
- `tests/integration` — сборка сервиса и контура настроек
- `tests/conversation` — сценарии пользовательского диалога
- `tests/security` — проверки безопасности конфигурации

Запуск:

```bash
pytest
ruff check .
mypy src tests
```

## Roadmap и UX-аудит

Подробный UX/конкурентный аудит и план следующих версий:
[docs/ux-competitive-roadmap.ru.md](docs/ux-competitive-roadmap.ru.md).

## Вклад в проект

Смотрите [CONTRIBUTING.md](CONTRIBUTING.md) и [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Безопасность

Смотрите [SECURITY.md](SECURITY.md).
