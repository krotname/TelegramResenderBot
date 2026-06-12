"""Unit tests for aiogram adapter wiring."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from aiogram import Dispatcher, Router

from telegram_resender.app import (
    build_service,
    create_dispatcher,
    create_router,
    incoming_from_message,
)
from telegram_resender.messages import (
    CAR_MODE_MESSAGE,
    HELP_MESSAGE,
    REQUEST_ACCEPTED_MESSAGE,
    RU_MESSAGES,
    START_MESSAGE,
)
from telegram_resender.settings import Settings


class FakeBot:
    """Minimal bot double used by the message forwarding handler."""

    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent_messages.append((chat_id, text))


class FakeMessage:
    """Minimal message double exposing only the fields handlers read."""

    def __init__(
        self,
        *,
        text: str | None = "Tower A, arrival 12:00, Ford, A123BC",
        username: str | None = "alice",
        bot: FakeBot | None = None,
    ) -> None:
        self.chat = SimpleNamespace(id=100)
        self.text = text
        self.message_id = 55
        self.date = datetime(2026, 6, 12, 10, 30, tzinfo=UTC)
        self.from_user = (
            SimpleNamespace(username=username, first_name="Alice", last_name="Tester")
            if username is not None
            else None
        )
        self._bot = bot
        self.answers: list[str] = []

    @property
    def bot(self) -> FakeBot | None:
        return self._bot

    async def answer(self, text: str) -> None:
        self.answers.append(text)


Handler = Callable[[Any], Awaitable[None]]


def _settings(tmp_path: Path) -> Settings:
    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("alice\n", encoding="utf-8")
    return Settings(
        bot_token="123:abc",
        forward_chat_id=200,
        whitelist_path=whitelist_path,
    )


def _message_handlers(router: Router) -> dict[str, Handler]:
    return {
        handler.callback.__name__: handler.callback
        for handler in router.observers["message"].handlers
    }


def test_incoming_from_message_handles_missing_fields() -> None:
    """Missing Telegram fields should become empty domain values."""

    incoming = incoming_from_message(FakeMessage(text=None, username=None))  # type: ignore[arg-type]

    assert incoming.chat_id == 100
    assert incoming.text == ""
    assert incoming.user.username is None
    assert incoming.user.first_name is None
    assert incoming.user.last_name is None
    assert incoming.message_id == 55
    assert incoming.submitted_at == datetime(2026, 6, 12, 10, 30, tzinfo=UTC)


@pytest.mark.asyncio
async def test_command_handlers_answer_static_messages(tmp_path: Path) -> None:
    """Static commands should answer without touching the forwarding service."""

    router = create_router(_settings(tmp_path), build_service(_settings(tmp_path)))
    handlers = _message_handlers(router)

    start_message = FakeMessage()
    help_message = FakeMessage()
    car_message = FakeMessage()
    template_message = FakeMessage()

    await handlers["start"](start_message)
    await handlers["help_command"](help_message)
    await handlers["car_mode"](car_message)
    await handlers["template"](template_message)

    assert start_message.answers == [START_MESSAGE]
    assert help_message.answers == [HELP_MESSAGE]
    assert car_message.answers == [CAR_MODE_MESSAGE]
    assert template_message.answers == [CAR_MODE_MESSAGE]


@pytest.mark.asyncio
async def test_forward_text_sends_whitelisted_message(tmp_path: Path) -> None:
    """Whitelisted users should be forwarded to the configured chat."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["forward_text"]
    bot = FakeBot()
    message = FakeMessage(bot=bot)

    await handler(message)

    assert message.answers == [REQUEST_ACCEPTED_MESSAGE]
    assert len(bot.sent_messages) == 1
    assert bot.sent_messages[0][0] == settings.forward_chat_id
    assert "Alice Tester (@alice)" in bot.sent_messages[0][1]
    assert "Request id: tg-100-55" in bot.sent_messages[0][1]


@pytest.mark.asyncio
async def test_forward_text_rejects_unknown_user(tmp_path: Path) -> None:
    """Unknown users should receive the denial response and not be forwarded."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["forward_text"]
    bot = FakeBot()
    message = FakeMessage(username="mallory", bot=bot)

    await handler(message)

    assert message.answers == [settings.messages.access_denied_unknown]
    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_forward_text_rejects_missing_username_with_chat_id(tmp_path: Path) -> None:
    """Users without a Telegram username should get an actionable denial."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["forward_text"]
    bot = FakeBot()
    message = FakeMessage(username=None, bot=bot)

    await handler(message)

    assert message.answers == [RU_MESSAGES.access_denied_missing_username.format(chat_id=100)]
    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_forward_text_rejects_incomplete_request(tmp_path: Path) -> None:
    """Whitelisted users should get template guidance for non-actionable text."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["forward_text"]
    bot = FakeBot()
    message = FakeMessage(text="hi", bot=bot)

    await handler(message)

    assert message.answers == [RU_MESSAGES.invalid_request]
    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_forward_text_requires_bound_bot(tmp_path: Path) -> None:
    """Forwarding should fail loudly if aiogram provides no bot instance."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["forward_text"]

    with pytest.raises(RuntimeError, match="not bound to a bot"):
        await handler(FakeMessage(bot=None))


@pytest.mark.asyncio
async def test_unsupported_messages_get_guidance(tmp_path: Path) -> None:
    """Non-text messages should not be silently ignored."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["unsupported_message"]
    message = FakeMessage(text=None, bot=FakeBot())

    await handler(message)

    assert message.answers == [RU_MESSAGES.unsupported_message]


def test_create_dispatcher_registers_router(tmp_path: Path) -> None:
    """Dispatcher construction should include the message router."""

    settings = _settings(tmp_path)
    dispatcher = create_dispatcher(settings, build_service(settings))

    assert isinstance(dispatcher, Dispatcher)
    assert dispatcher.sub_routers
