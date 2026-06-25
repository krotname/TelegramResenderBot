"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from asyncio import run as asyncio_run
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import TextIO

from aiogram.exceptions import TelegramAPIError
from pydantic import ValidationError

from telegram_resender.app import run_polling
from telegram_resender.routes import default_route, load_routes
from telegram_resender.settings import Settings
from telegram_resender.storage import RequestLog, export_records_csv
from telegram_resender.whitelist import Whitelist


def main(argv: Sequence[str] | None = None) -> None:
    """Run the Telegram bot CLI."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        raise SystemExit(run_doctor(storage_check=args.storage_check))
    if args.command == "export-requests":
        raise SystemExit(export_requests(since=args.since))
    if args.command == "health":
        raise SystemExit(run_health())
    raise SystemExit(run_bot(debug=args.debug))


def run_bot(*, debug: bool = False) -> int:
    """Start polling and turn expected startup failures into CLI errors."""

    try:
        asyncio_run(run_polling())
    except (ValidationError, FileNotFoundError, TelegramAPIError, ValueError) as exc:
        _print_startup_error(exc, debug=debug)
        return 2
    return 0


def run_doctor(
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    *,
    storage_check: bool = False,
) -> int:
    """Validate local configuration without starting Telegram polling."""

    try:
        settings = Settings()  # type: ignore[call-arg]
        whitelist = Whitelist.from_file(settings.whitelist_path)
        routes = (
            load_routes(settings.routes_path)
            if settings.routes_path is not None
            else (default_route(settings.forward_chat_id),)
        )
        if storage_check:
            RequestLog(settings.storage_path).check()
    except ValidationError as exc:
        print(_format_validation_error(exc), file=stderr)
        return 2
    except (FileNotFoundError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=stderr)
        print(_setup_hint(), file=stderr)
        return 2

    print("Telegram Resender doctor", file=stdout)
    print("Configuration: OK", file=stdout)
    print(f"Locale: {settings.locale}", file=stdout)
    print(f"Forward chat id: {settings.forward_chat_id}", file=stdout)
    print(f"Whitelist path: {_display_path(settings.whitelist_path)}", file=stdout)
    print(f"Whitelist users: {len(whitelist.user_ids)}", file=stdout)
    print(f"Routes path: {_display_optional_path(settings.routes_path)}", file=stdout)
    print(f"Routes: {len(routes)}", file=stdout)
    print(f"Storage path: {_display_path(settings.storage_path)}", file=stdout)
    print(f"Storage check: {'OK' if storage_check else 'not requested'}", file=stdout)
    print(f"Admin users: {len(settings.admin_ids)}", file=stdout)
    print(f"Confirm before forward: {settings.confirm_before_forward}", file=stdout)
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
    doctor_parser = subparsers.add_parser("doctor", help="validate configuration without polling")
    doctor_parser.add_argument(
        "--storage-check",
        action="store_true",
        help="open SQLite storage and ensure delivery log schema exists",
    )
    export_parser = subparsers.add_parser(
        "export-requests",
        help="export delivery log rows as CSV",
    )
    export_parser.add_argument("--since", required=True, help="inclusive date in YYYY-MM-DD format")
    subparsers.add_parser("health", help="minimal health check for process managers")
    return parser


def run_health(stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    """Run a concise health check for process managers."""

    try:
        settings = Settings()  # type: ignore[call-arg]
        Whitelist.from_file(settings.whitelist_path)
        if settings.routes_path is not None:
            load_routes(settings.routes_path)
        RequestLog(settings.storage_path).check()
    except (ValidationError, FileNotFoundError, ValueError, OSError) as exc:
        print(f"health=error error={exc}", file=stderr)
        return 2
    print("health=ok", file=stdout)
    return 0


def export_requests(
    *,
    since: str,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Export request delivery records as CSV."""

    try:
        settings = Settings()  # type: ignore[call-arg]
        since_date = date.fromisoformat(since)
        records = RequestLog(settings.storage_path).records_since(since_date)
    except (ValidationError, ValueError, OSError) as exc:
        print(f"Export error: {exc}", file=stderr)
        return 2
    export_records_csv(records, stdout)
    return 0


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


def _display_optional_path(path: Path | None) -> str:
    return _display_path(path) if path is not None else "<default single route>"
