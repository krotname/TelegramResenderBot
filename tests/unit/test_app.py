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

VALID_REQUEST = (
    "Объект/здание: Башня А\n"
    "Дата и время прибытия: 12.06.2026 10:30\n"
    "Автомобиль: Ford Focus\n"
    "Госномер: А123ВС"
)


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
        text: str | None = VALID_REQUEST,
        username: str | None = "alice",
        user_id: int | None = 10,
        bot: FakeBot | None = None,
    ) -> None:
        self.chat = SimpleNamespace(id=100)
        self.text = text
        self.message_id = 55
        self.date = datetime(2026, 6, 12, 10, 30, tzinfo=UTC)
        self.from_user = (
            SimpleNamespace(
                id=user_id,
                username=username,
                first_name="Alice",
                last_name="Tester",
            )
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


def _settings(tmp_path: Path, *, confirm_before_forward: bool = False) -> Settings:
    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("10\n", encoding="utf-8")
    return Settings(
        bot_token="123:abc",
        forward_chat_id=200,
        whitelist_path=whitelist_path,
        storage_path=tmp_path / "requests.sqlite3",
        confirm_before_forward=confirm_before_forward,
        admin_ids_raw="10",
    )


def _settings_with_routes(tmp_path: Path) -> Settings:
    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("10\n", encoding="utf-8")
    routes_path = tmp_path / "routes.json"
    routes_path.write_text(
        """
        {
          "routes": [
            {"name": "primary", "target_chat_id": 200},
            {"name": "tower", "target_chat_id": 300, "keywords_any": ["Башня"]}
          ]
        }
        """,
        encoding="utf-8",
    )
    return Settings(
        bot_token="123:abc",
        forward_chat_id=999,
        whitelist_path=whitelist_path,
        routes_path=routes_path,
        storage_path=tmp_path / "requests.sqlite3",
        admin_ids_raw="10",
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
async def test_whoami_reports_user_and_chat_ids(tmp_path: Path) -> None:
    """Any user should be able to inspect their ids for admin setup."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["whoami"]
    message = FakeMessage(user_id=777)

    await handler(message)

    assert message.answers == [RU_MESSAGES.whoami.format(user_id=777, chat_id=100)]


@pytest.mark.asyncio
async def test_admin_status_requires_admin_id(tmp_path: Path) -> None:
    """Admin commands should reject users outside TELEGRAM_RESENDER_ADMIN_IDS."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["admin_status"]
    message = FakeMessage(user_id=999)

    await handler(message)

    assert message.answers == [RU_MESSAGES.admin_access_denied]


@pytest.mark.asyncio
async def test_admin_status_reports_runtime_state(tmp_path: Path) -> None:
    """Admins should see operational state without shell access."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["admin_status"]
    message = FakeMessage(user_id=10)

    await handler(message)

    assert "Whitelist users: 1" in message.answers[0]
    assert "Admin users: 1" in message.answers[0]
    assert "Confirm before forward: True" in message.answers[0]


@pytest.mark.asyncio
async def test_admin_can_reload_whitelist(tmp_path: Path) -> None:
    """Whitelist reload should update forwarding decisions without restarting."""

    settings = _settings(tmp_path)
    service = build_service(settings)
    router = create_router(settings, service)
    handlers = _message_handlers(router)
    whitelist_path = settings.whitelist_path
    whitelist_path.write_text("10\n999\n", encoding="utf-8")
    admin = FakeMessage(user_id=10)

    await handlers["reload_whitelist"](admin)

    assert admin.answers == [RU_MESSAGES.whitelist_reloaded.format(count=2)]
    bot = FakeBot()
    message = FakeMessage(username="mallory", user_id=999, bot=bot)
    await handlers["forward_text"](message)
    assert message.answers == [REQUEST_ACCEPTED_MESSAGE]
    assert len(bot.sent_messages) == 1


@pytest.mark.asyncio
async def test_admin_can_query_whitelist_count(tmp_path: Path) -> None:
    """Admins should be able to query the current whitelist size."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["whitelist_count"]
    message = FakeMessage(user_id=10)

    await handler(message)

    assert message.answers == [RU_MESSAGES.whitelist_count.format(count=1)]


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
async def test_forward_text_skips_already_delivered_request(tmp_path: Path) -> None:
    """The delivery log should make repeated request ids idempotent per target."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["forward_text"]
    bot = FakeBot()

    await handler(FakeMessage(bot=bot))
    await handler(FakeMessage(bot=bot))

    assert len(bot.sent_messages) == 1


@pytest.mark.asyncio
async def test_forward_text_uses_matching_routes(tmp_path: Path) -> None:
    """Routes config should override the default forward chat target."""

    settings = _settings_with_routes(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["forward_text"]
    bot = FakeBot()
    message = FakeMessage(bot=bot)

    await handler(message)

    assert message.answers == [REQUEST_ACCEPTED_MESSAGE]
    assert bot.sent_messages == [
        (200, bot.sent_messages[0][1]),
        (300, bot.sent_messages[1][1]),
    ]
    assert "Request id: tg-100-55" in bot.sent_messages[0][1]


@pytest.mark.asyncio
async def test_forward_text_can_require_confirmation(tmp_path: Path) -> None:
    """Confirmation mode should show a preview and wait for /confirm."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    router = create_router(settings, build_service(settings))
    handlers = _message_handlers(router)
    bot = FakeBot()
    message = FakeMessage(bot=bot)

    await handlers["forward_text"](message)

    assert bot.sent_messages == []
    assert "tg-100-55" in message.answers[0]
    assert "/confirm" in message.answers[0]

    confirm = FakeMessage(bot=bot)
    await handlers["confirm_request"](confirm)

    assert confirm.answers == [RU_MESSAGES.request_confirmed.format(request_id="tg-100-55")]
    assert len(bot.sent_messages) == 1
    assert "Request id: tg-100-55" in bot.sent_messages[0][1]


@pytest.mark.asyncio
async def test_confirmation_can_be_cancelled(tmp_path: Path) -> None:
    """Pending confirmation should be cancellable without forwarding."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    router = create_router(settings, build_service(settings))
    handlers = _message_handlers(router)
    bot = FakeBot()
    message = FakeMessage(bot=bot)

    await handlers["forward_text"](message)
    cancel = FakeMessage(bot=bot)
    await handlers["cancel_request"](cancel)

    assert cancel.answers == [RU_MESSAGES.request_cancelled.format(request_id="tg-100-55")]
    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_confirm_without_pending_request_gets_guidance(tmp_path: Path) -> None:
    """Users should know when there is nothing to confirm."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["confirm_request"]
    message = FakeMessage(bot=FakeBot())

    await handler(message)

    assert message.answers == [RU_MESSAGES.no_pending_request]


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
