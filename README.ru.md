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
- Опциональные multi-route правила через `routes.json`.
- SQLite delivery log, retry/backoff и идемпотентность по request id.
- Docker, docker-compose, systemd и health-check для production.
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
| `TELEGRAM_RESENDER_ROUTES_PATH` | нет | путь к JSON-файлу маршрутов |
| `TELEGRAM_RESENDER_LOCALE` | нет | `ru` или `en`, по умолчанию `ru` |
| `TELEGRAM_RESENDER_CONFIRM_BEFORE_FORWARD` | нет | `true`, чтобы показывать preview и ждать `/confirm` |
| `TELEGRAM_RESENDER_ADMIN_IDS` | нет | Telegram user id администраторов через запятую |
| `TELEGRAM_RESENDER_STORAGE_PATH` | нет | SQLite delivery log, по умолчанию `telegram_resender.sqlite3` |
| `TELEGRAM_RESENDER_DELIVERY_MAX_ATTEMPTS` | нет | попытки отправки в Telegram, по умолчанию `3` |
| `TELEGRAM_RESENDER_DELIVERY_RETRY_BACKOFF` | нет | базовая задержка retry в секундах |
| `TELEGRAM_RESENDER_LOG_LEVEL` | нет | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `TELEGRAM_RESENDER_LOG_FORMAT` | нет | `TEXT` или `JSON`, по умолчанию `TEXT` |
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

## Маршруты

Если `TELEGRAM_RESENDER_ROUTES_PATH` не задан, бот использует один маршрут из
`TELEGRAM_RESENDER_FORWARD_CHAT_ID`. Для нескольких целей создайте JSON по образцу
[routes.example.json](routes.example.json):

```json
{
  "routes": [
    {
      "name": "tower-a",
      "target_chat_id": -1002222222222,
      "allowed_usernames": ["building_admin"],
      "keywords_any": ["Башня А"],
      "keywords_none": ["отмена"],
      "template": "[{route}]\n{request}",
      "enabled": true
    }
  ]
}
```

Заявка отправляется во все активные маршруты, где совпали пользователь и keyword-фильтры.

## Надежность доставки

Бот ведет SQLite-журнал доставок. Для каждой пары `request_id + target_chat_id`
хранится статус `pending`, `delivered` или `failed`, отправитель и последняя ошибка.
Если такая пара уже доставлена, повторная обработка того же request id не отправит
сообщение второй раз.

```bash
telegram-resender doctor --storage-check
telegram-resender health
telegram-resender export-requests --since 2026-06-12
```

## Развертывание

Docker:

```bash
copy .env.production.example .env.production
mkdir data
copy whitelist.example.csv data\whitelist.csv
docker compose up -d --build
```

Systemd пример лежит в [deploy/telegram-resender.service](deploy/telegram-resender.service).
Production env template: [.env.production.example](.env.production.example).

Для production-логов включите:

```env
TELEGRAM_RESENDER_LOG_FORMAT=JSON
```

## Релизы и Supply Chain

- Docker base image закреплен по digest в [Dockerfile](Dockerfile).
- Python runtime/dev/audit зависимости ставятся из hash-locked файлов `requirements*.lock`.
- GitHub Actions закреплены по commit SHA.
- Релизный workflow собирает wheel и sdist, публикует `SHA256SUMS.txt` и GitHub provenance attestation.
- Правила обновления зависимостей описаны в [docs/DEPENDENCY_POLICY.md](docs/DEPENDENCY_POLICY.md).

Проверка релизных артефактов:

```bash
sha256sum -c SHA256SUMS.txt
gh attestation verify telegram_resender-*.whl --repo krotname/TelegramResenderBot
```

## Ограничения

- Это bot-based intake/forwarding, не userbot.
- Бот не обходит protected/restricted Telegram-чаты.
- Медиа, документы, voice и polls пока не пересылаются как payload.
- AI rewrite/translate/digest не реализованы.
- Hosted SaaS, mobile app и web dashboard не входят в текущую self-hosted область.

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

Смотрите [SECURITY.md](SECURITY.md) и [docs/DEPENDENCY_POLICY.md](docs/DEPENDENCY_POLICY.md).
