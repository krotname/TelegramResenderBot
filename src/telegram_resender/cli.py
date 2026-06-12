"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from asyncio import run as asyncio_run
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from aiogram.exceptions import TelegramAPIError
from pydantic import ValidationError

from telegram_resender.app import run_polling
from telegram_resender.settings import Settings
from telegram_resender.whitelist import Whitelist


def main(argv: Sequence[str] | None = None) -> None:
    """Run the Telegram bot CLI."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        raise SystemExit(run_doctor())
    raise SystemExit(run_bot(debug=args.debug))


def run_bot(*, debug: bool = False) -> int:
    """Start polling and turn expected startup failures into CLI errors."""

    try:
        asyncio_run(run_polling())
    except (ValidationError, FileNotFoundError, TelegramAPIError, ValueError) as exc:
        _print_startup_error(exc, debug=debug)
        return 2
    return 0


def run_doctor(stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    """Validate local configuration without starting Telegram polling."""

    try:
        settings = Settings()  # type: ignore[call-arg]
        whitelist = Whitelist.from_file(settings.whitelist_path)
    except ValidationError as exc:
        print(_format_validation_error(exc), file=stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"Configuration error: {exc}", file=stderr)
        print(_setup_hint(), file=stderr)
        return 2

    print("Telegram Resender doctor", file=stdout)
    print("Configuration: OK", file=stdout)
    print(f"Locale: {settings.locale}", file=stdout)
    print(f"Forward chat id: {settings.forward_chat_id}", file=stdout)
    print(f"Whitelist path: {_display_path(settings.whitelist_path)}", file=stdout)
    print(f"Whitelist users: {len(whitelist.usernames)}", file=stdout)
    print(f"Polling timeout: {settings.polling_timeout}s", file=stdout)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="telegram-resender")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="show Python traceback for startup errors",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="start Telegram polling")
    subparsers.add_parser("doctor", help="validate configuration without polling")
    return parser


def _print_startup_error(exc: Exception, *, debug: bool) -> None:
    if debug:
        raise exc
    if isinstance(exc, ValidationError):
        print(_format_validation_error(exc), file=sys.stderr)
    else:
        print(f"Startup error: {exc}", file=sys.stderr)
        print(_setup_hint(), file=sys.stderr)


def _format_validation_error(exc: ValidationError) -> str:
    lines = ["Configuration error:"]
    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"])
        lines.append(f"- {field}: {error['msg']}")
    lines.append(_setup_hint())
    return "\n".join(lines)


def _setup_hint() -> str:
    return (
        "Create .env from .env.example and fill TELEGRAM_RESENDER_BOT_TOKEN, "
        "TELEGRAM_RESENDER_FORWARD_CHAT_ID, and TELEGRAM_RESENDER_WHITELIST_PATH."
    )


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)
