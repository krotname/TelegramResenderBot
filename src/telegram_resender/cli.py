"""Command line entry point."""

from __future__ import annotations

import asyncio

from telegram_resender.app import run_polling


def main() -> None:
    """Start the Telegram bot using environment-based settings."""

    asyncio.run(run_polling())
