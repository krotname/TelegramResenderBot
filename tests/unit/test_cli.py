"""Unit tests for the command-line entry point."""

import sqlite3
from collections.abc import Coroutine
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from telegram_resender import cli
from telegram_resender.settings import Settings
from telegram_resender.storage import RequestLog

VALID_BOT_TOKEN = f"123456789:{'A' * 35}"


def test_main_runs_polling(monkeypatch: Any) -> None:
    """The CLI should delegate to the async polling runner."""

    called = False

    async def fake_run_polling() -> None:
        nonlocal called
        called = True

    def run_coroutine(coro: Coroutine[Any, Any, None]) -> None:
        coro.close()
        nonlocal called
        called = True

    monkeypatch.setattr(cli, "run_polling", fake_run_polling)
    monkeypatch.setattr(cli, "asyncio_run", run_coroutine)

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert called is True
    assert exc_info.value.code == 0


def test_run_bot_formats_validation_errors(monkeypatch: Any, capsys: Any) -> None:
    """Startup config errors should not expose raw tracebacks by default."""

    async def fail_validation() -> None:
        Settings(bot_token="changeme", forward_chat_id=1)

    monkeypatch.setattr(cli, "run_polling", fail_validation)

    assert cli.run_bot() == 2
    captured = capsys.readouterr()
    assert "Configuration error:" in captured.err
    assert "Traceback" not in captured.err


def test_doctor_reports_loaded_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doctor should validate settings and whitelist without polling Telegram."""

    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("10\n20\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_RESENDER_BOT_TOKEN", VALID_BOT_TOKEN)
    monkeypatch.setenv("TELEGRAM_RESENDER_FORWARD_CHAT_ID", "100")
    monkeypatch.setenv("TELEGRAM_RESENDER_WHITELIST_PATH", str(whitelist_path))
    monkeypatch.setenv("TELEGRAM_RESENDER_STORAGE_PATH", str(tmp_path / "requests.sqlite3"))

    stdout = StringIO()
    stderr = StringIO()

    assert cli.run_doctor(stdout=stdout, stderr=stderr, storage_check=True) == 0
    assert "Configuration: OK" in stdout.getvalue()
    assert "Whitelist users: 2" in stdout.getvalue()
    assert "Routes: 1" in stdout.getvalue()
    assert "Storage check: OK" in stdout.getvalue()
    assert "Admin users: 0" in stdout.getvalue()
    assert "Confirm before forward: False" in stdout.getvalue()
    assert "Pending request TTL: 900s" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_export_requests_outputs_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The export command should print delivery records as CSV."""

    storage_path = tmp_path / "requests.sqlite3"
    request_log = RequestLog(storage_path)
    lease = request_log.begin_delivery(
        request_id="req-1",
        target_chat_id=100,
        sender_username="alice",
    )
    assert lease is not None
    request_log.mark_delivery(lease=lease, status="delivered")
    monkeypatch.setenv("TELEGRAM_RESENDER_BOT_TOKEN", VALID_BOT_TOKEN)
    monkeypatch.setenv("TELEGRAM_RESENDER_FORWARD_CHAT_ID", "100")
    monkeypatch.setenv("TELEGRAM_RESENDER_STORAGE_PATH", str(storage_path))
    stdout = StringIO()
    stderr = StringIO()

    assert cli.export_requests(since="2000-01-01", stdout=stdout, stderr=stderr) == 0

    assert "req-1,100,alice" in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_health_reports_ok_for_valid_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Health should be concise for process managers."""

    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("10\n", encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_RESENDER_BOT_TOKEN", VALID_BOT_TOKEN)
    monkeypatch.setenv("TELEGRAM_RESENDER_FORWARD_CHAT_ID", "100")
    monkeypatch.setenv("TELEGRAM_RESENDER_WHITELIST_PATH", str(whitelist_path))
    monkeypatch.setenv("TELEGRAM_RESENDER_STORAGE_PATH", str(tmp_path / "requests.sqlite3"))
    stdout = StringIO()
    stderr = StringIO()

    assert cli.run_health(stdout=stdout, stderr=stderr) == 0

    assert stdout.getvalue() == "health=ok\n"
    assert stderr.getvalue() == ""


def test_health_reports_sqlite_errors_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unusable storage path should produce a normal health-check failure."""

    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("10\n", encoding="utf-8")
    monkeypatch.setenv("TELEGRAM_RESENDER_BOT_TOKEN", VALID_BOT_TOKEN)
    monkeypatch.setenv("TELEGRAM_RESENDER_FORWARD_CHAT_ID", "100")
    monkeypatch.setenv("TELEGRAM_RESENDER_WHITELIST_PATH", str(whitelist_path))
    monkeypatch.setenv("TELEGRAM_RESENDER_STORAGE_PATH", str(tmp_path))
    stdout = StringIO()
    stderr = StringIO()

    assert cli.run_health(stdout=stdout, stderr=stderr) == 2

    assert stdout.getvalue() == ""
    assert "health=error" in stderr.getvalue()


def test_health_rejects_incompatible_sqlite_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Health must validate the delivery table rather than only its name."""

    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("10\n", encoding="utf-8")
    storage_path = tmp_path / "requests.sqlite3"
    connection = sqlite3.connect(storage_path)
    try:
        connection.execute("CREATE TABLE request_deliveries (request_id TEXT)")
        connection.commit()
    finally:
        connection.close()
    monkeypatch.setenv("TELEGRAM_RESENDER_BOT_TOKEN", VALID_BOT_TOKEN)
    monkeypatch.setenv("TELEGRAM_RESENDER_FORWARD_CHAT_ID", "100")
    monkeypatch.setenv("TELEGRAM_RESENDER_WHITELIST_PATH", str(whitelist_path))
    monkeypatch.setenv("TELEGRAM_RESENDER_STORAGE_PATH", str(storage_path))
    stdout = StringIO()
    stderr = StringIO()

    assert cli.run_health(stdout=stdout, stderr=stderr) == 2

    assert stdout.getvalue() == ""
    assert "schema mismatch" in stderr.getvalue()


def test_run_bot_formats_sqlite_startup_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    """SQLite startup failures should use the same concise CLI error path."""

    async def fail_storage() -> None:
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(cli, "run_polling", fail_storage)

    assert cli.run_bot() == 2
    captured = capsys.readouterr()
    assert "Startup error: unable to open database file" in captured.err
    assert "Traceback" not in captured.err


def test_health_does_not_echo_invalid_bot_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configuration errors must not leak the bot token into logs."""

    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("10\n", encoding="utf-8")
    leaked_token = f"123456789:{'S' * 34}"
    monkeypatch.setenv("TELEGRAM_RESENDER_BOT_TOKEN", leaked_token)
    monkeypatch.setenv("TELEGRAM_RESENDER_FORWARD_CHAT_ID", "100")
    monkeypatch.setenv("TELEGRAM_RESENDER_WHITELIST_PATH", str(whitelist_path))
    monkeypatch.setenv("TELEGRAM_RESENDER_STORAGE_PATH", str(tmp_path / "requests.sqlite3"))
    stdout = StringIO()
    stderr = StringIO()

    assert cli.run_health(stdout=stdout, stderr=stderr) == 2

    assert stdout.getvalue() == ""
    assert "health=error" in stderr.getvalue()
    assert leaked_token not in stderr.getvalue()


def test_export_requests_does_not_echo_invalid_bot_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CSV export must not leak the bot token when settings fail validation."""

    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("10\n", encoding="utf-8")
    leaked_token = f"123456789:{'S' * 34}"
    monkeypatch.setenv("TELEGRAM_RESENDER_BOT_TOKEN", leaked_token)
    monkeypatch.setenv("TELEGRAM_RESENDER_FORWARD_CHAT_ID", "100")
    monkeypatch.setenv("TELEGRAM_RESENDER_WHITELIST_PATH", str(whitelist_path))
    monkeypatch.setenv("TELEGRAM_RESENDER_STORAGE_PATH", str(tmp_path / "requests.sqlite3"))
    stdout = StringIO()
    stderr = StringIO()

    assert cli.export_requests(since="2026-01-01", stdout=stdout, stderr=stderr) == 2

    assert stdout.getvalue() == ""
    assert "Configuration error" in stderr.getvalue()
    assert leaked_token not in stderr.getvalue()
