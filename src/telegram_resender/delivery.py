"""Reliable Telegram delivery helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

SendMessage = Callable[[int, str], Awaitable[object]]
Sleep = Callable[[float], Awaitable[None]]
BeforeRetryWait = Callable[[float], None]


async def send_with_retry(
    send_message: SendMessage,
    *,
    chat_id: int,
    text: str,
    max_attempts: int,
    backoff_seconds: float,
    sleep: Sleep = asyncio.sleep,
    before_retry_wait: BeforeRetryWait | None = None,
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
            delay = float(exc.retry_after)
            if before_retry_wait is not None:
                before_retry_wait(delay)
            await sleep(delay)
        except TelegramAPIError:
            if attempt >= max_attempts:
                raise
            delay = backoff_seconds * attempt
            if before_retry_wait is not None:
                before_retry_wait(delay)
            await sleep(delay)
        attempt += 1
