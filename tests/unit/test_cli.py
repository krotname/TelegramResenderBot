"""Unit tests for the command-line entry point."""

import asyncio
from collections.abc import Coroutine
from typing import Any

from telegram_resender import cli


def test_main_runs_polling(monkeypatch: Any) -> None:
    """The CLI should delegate to the async polling runner."""

    called = False

    async def fake_run_polling() -> None:
        nonlocal called
        called = True

    def run_coroutine(coro: Coroutine[Any, Any, None]) -> None:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()

    monkeypatch.setattr(cli, "run_polling", fake_run_polling)
    monkeypatch.setattr(cli.asyncio, "run", run_coroutine)

    cli.main()

    assert called is True
