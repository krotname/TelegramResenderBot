# Telegram Resender

[![CI](https://github.com/krotname/TelegramResenderBot/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/krotname/TelegramResenderBot/actions/workflows/ci.yml?query=branch%3Amaster)
[![CodeQL](https://github.com/krotname/TelegramResenderBot/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/krotname/TelegramResenderBot/actions/workflows/codeql.yml?query=branch%3Amaster)
[![Coverage Gate](https://img.shields.io/badge/coverage%20gate-70%25%2B-2ea44f)](docs/testing.md)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/krotname/TelegramResenderBot/badge)](https://securityscorecards.dev/viewer/?uri=github.com/krotname/TelegramResenderBot)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776ab)](https://www.python.org/downloads/)

[🇷🇺 README](README.ru.md)

## Overview

Telegram Resender is a focused bot that checks incoming text messages against a whitelist of
Telegram usernames and forwards approved requests to a configured target chat.

The project is intentionally small and practical:

- environment-based configuration only
- typed settings and dependency injection
- separated domain logic and transport handler layer
- strict linters and tests as CI defaults

## Features

- `/start`, `/help`, `/template`, `/avto` commands
- whitelist-based access control
- localized Russian and English bot messages
- separate guidance for unknown users, missing Telegram usernames, and incomplete requests
- unsupported message guidance for photos, documents, stickers, and voice messages
- deterministic formatting of forwarded messages with request id and submitted time
- strict startup validation for secrets and a `doctor` diagnostics command
- unit, integration, conversation and security test categories
- GitHub Actions CI (lint, typing, tests, CodeQL, dependency review)
- OpenSSF Scorecard workflow with SARIF upload and public API badge publishing

## Quick start

1. Install Python 3.12+.
2. Create `.env` based on `.env.example`.
3. Run:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
copy .env.example .env      # Windows
# or: cp .env.example .env  # Linux/macOS
telegram-resender doctor
telegram-resender
```

Windows and Linux share the same startup command.

## Configuration

All settings are read from environment variables (or `.env`).

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_RESENDER_BOT_TOKEN` | yes | Telegram bot token |
| `TELEGRAM_RESENDER_FORWARD_CHAT_ID` | yes | target chat/group ID |
| `TELEGRAM_RESENDER_WHITELIST_PATH` | no | CSV path, default `whitelist.csv` |
| `TELEGRAM_RESENDER_LOCALE` | no | `ru` or `en`, default `ru` |
| `TELEGRAM_RESENDER_REQUEST_ACCEPTED_MESSAGE` | no | text returned on success |
| `TELEGRAM_RESENDER_ACCESS_DENIED_MESSAGE` | no | text returned to unknown users |
| `TELEGRAM_RESENDER_LOG_LEVEL` | no | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `TELEGRAM_RESENDER_POLLING_TIMEOUT` | no | Polling timeout, default `30` |

Whitelist format:

```csv
# whitelist.csv
alice
@bob
```

## Request format

Users can call `/template` or `/avto` and send a text request:

```text
Building: Tower A
Arrival date and time: 2026-06-12 10:30
Vehicle: Ford Focus
License plate: A123BC
Comment: meeting with facilities
```

The bot currently accepts text only. Media and documents are not forwarded.

## Development

```bash
pip install -e .[dev]
ruff check .
mypy src tests
pytest
```

### Test categories

- Unit tests: `tests/unit/*`
- Integration tests: `tests/integration/*`
- Conversation tests: `tests/conversation/*`
- Security tests: `tests/security/*`

## Architecture

- `whitelist.py` — input parsing and membership checks.
- `service.py` — pure decision logic and policy.
- `formatting.py` — deterministic outbound payloads.
- `app.py` — aiogram handlers and Telegram transport wiring.
- `settings.py` — validated configuration.
- `cli.py` — process start command.
- `__main__.py` — module entrypoint alias for `python -m telegram_resender`.

## Contribution

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

GPL-3.0 License. See [LICENSE](LICENSE).

## Design docs

- [Architecture](docs/architecture.md)
- [Testing strategy](docs/testing.md)
- [UX and competitive roadmap](docs/ux-competitive-roadmap.ru.md)

---

English and Russian users can find mirrored information in both languages:

- [README.en.md (English)](README.en.md)
- [README.md (Russian, primary)](README.md)
- [README.ru.md (Russian)](README.ru.md)
