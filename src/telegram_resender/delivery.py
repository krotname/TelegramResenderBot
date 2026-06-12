"""Reliable Telegram delivery helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

SendMessage = Callable[[int, str], Awaitable[object]]
Sleep = Callable[[float], Awaitable[None]]


async def send_with_retry(
    send_message: SendMessage,
    *,
    chat_id: int,
    text: str,
    max_attempts: int,
    backoff_seconds: float,
    sleep: Sleep = asyncio.sleep,
) -> None:
    """Send a Telegram message with bounded retry/backoff for API failures."""

    attempt = 1
    while True:
        try:
            await send_message(chat_id, text)
            return
        except TelegramRetryAfter as exc:
            if attempt >= max_attempts:
                raise
            await sleep(float(exc.retry_after))
        except TelegramAPIError:
            if attempt >= max_attempts:
                raise
            await sleep(backoff_seconds * attempt)
        attempt += 1
