"""Unit tests for reliable delivery helpers."""

import pytest
from aiogram.exceptions import TelegramAPIError
from aiogram.methods import SendMessage

from telegram_resender.delivery import send_with_retry


@pytest.mark.asyncio
async def test_send_with_retry_retries_telegram_api_errors() -> None:
    """Transient Telegram API errors should be retried with backoff."""

    attempts = 0
    sleeps: list[float] = []

    async def fake_send(chat_id: int, text: str) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TelegramAPIError(
                method=SendMessage(chat_id=chat_id, text=text),
                message="temporary",
            )

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    await send_with_retry(
        fake_send,
        chat_id=100,
        text="payload",
        max_attempts=2,
        backoff_seconds=0.5,
        sleep=fake_sleep,
    )

    assert attempts == 2
    assert sleeps == [0.5]


@pytest.mark.asyncio
async def test_send_with_retry_raises_after_max_attempts() -> None:
    """Persistent Telegram API errors should surface after the retry budget."""

    async def fake_send(chat_id: int, text: str) -> None:
        raise TelegramAPIError(
            method=SendMessage(chat_id=chat_id, text=text),
            message="persistent",
        )

    async def fake_sleep(delay: float) -> None:
        return None

    with pytest.raises(TelegramAPIError):
        await send_with_retry(
            fake_send,
            chat_id=100,
            text="payload",
            max_attempts=2,
            backoff_seconds=0.5,
            sleep=fake_sleep,
        )
