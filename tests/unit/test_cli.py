"""Unit tests for the command-line entry point."""

from collections.abc import Coroutine
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from telegram_resender import cli
from telegram_resender.settings import Settings


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
    whitelist_path.write_text("alice\nbob\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_RESENDER_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_RESENDER_FORWARD_CHAT_ID", "100")
    monkeypatch.setenv("TELEGRAM_RESENDER_WHITELIST_PATH", str(whitelist_path))

    stdout = StringIO()
    stderr = StringIO()

    assert cli.run_doctor(stdout=stdout, stderr=stderr) == 0
    assert "Configuration: OK" in stdout.getvalue()
    assert "Whitelist users: 2" in stdout.getvalue()
    assert stderr.getvalue() == ""
