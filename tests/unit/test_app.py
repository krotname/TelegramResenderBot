"""Unit tests for aiogram adapter wiring."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from aiogram import Dispatcher, Router

import telegram_resender.storage as storage_module
from telegram_resender.app import (
    build_service,
    create_dispatcher,
    create_router,
    incoming_from_message,
)
from telegram_resender.formatting import MessageFormatter
from telegram_resender.messages import (
    CAR_MODE_MESSAGE,
    HELP_MESSAGE,
    REQUEST_ACCEPTED_MESSAGE,
    RU_MESSAGES,
    START_MESSAGE,
)
from telegram_resender.settings import Settings
from telegram_resender.storage import RequestLog

VALID_REQUEST = (
    "Объект/здание: Башня А\n"
    "Дата и время прибытия: 12.06.2026 10:30\n"
    "Автомобиль: Ford Focus\n"
    "Госномер: А123ВС"
)
VALID_BOT_TOKEN = f"123456789:{'A' * 35}"


class FakeBot:
    """Minimal bot double used by the message forwarding handler."""

    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent_messages.append((chat_id, text))


class FailOnceBot(FakeBot):
    """Bot double that simulates one delivery failure before succeeding."""

    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    async def send_message(self, chat_id: int, text: str) -> None:
        self.attempts += 1
        if self.attempts == 1:
            raise RuntimeError("temporary delivery failure")
        await super().send_message(chat_id, text)


class BlockingFailOnceBot(FakeBot):
    """Hold the first delivery open so another request can be published concurrently."""

    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.attempts = 0

    async def send_message(self, chat_id: int, text: str) -> None:
        self.attempts += 1
        if self.attempts == 1:
            self.started.set()
            await self.release.wait()
            raise RuntimeError("temporary delivery failure")
        await super().send_message(chat_id, text)


class BlockingBot(FakeBot):
    """Hold a successful delivery open to expose duplicate in-flight claims."""

    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.attempts = 0

    async def send_message(self, chat_id: int, text: str) -> None:
        self.attempts += 1
        self.started.set()
        await self.release.wait()
        await super().send_message(chat_id, text)


class FakeMessage:
    """Minimal message double exposing only the fields handlers read."""

    def __init__(
        self,
        *,
        text: str | None = VALID_REQUEST,
        username: str | None = "alice",
        user_id: int | None = 10,
        bot: FakeBot | None = None,
        chat_id: int = 100,
        message_id: int | None = 55,
    ) -> None:
        self.chat = SimpleNamespace(id=chat_id)
        self.text = text
        self.message_id = message_id
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


class FailingAnswerMessage(FakeMessage):
    """Message double whose Telegram reply fails before a preview is published."""

    async def answer(self, text: str) -> None:
        raise RuntimeError("preview delivery failed")


Handler = Callable[[Any], Awaitable[None]]


def _settings(
    tmp_path: Path,
    *,
    confirm_before_forward: bool = False,
    pending_request_ttl_seconds: int = 900,
) -> Settings:
    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("10\n", encoding="utf-8")
    return Settings(
        bot_token=VALID_BOT_TOKEN,
        forward_chat_id=200,
        whitelist_path=whitelist_path,
        storage_path=tmp_path / "requests.sqlite3",
        confirm_before_forward=confirm_before_forward,
        pending_request_ttl_seconds=pending_request_ttl_seconds,
        admin_ids_raw="10",
    )


def _settings_with_routes(tmp_path: Path, *, confirm_before_forward: bool = False) -> Settings:
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
        bot_token=VALID_BOT_TOKEN,
        forward_chat_id=999,
        whitelist_path=whitelist_path,
        routes_path=routes_path,
        storage_path=tmp_path / "requests.sqlite3",
        admin_ids_raw="10",
        confirm_before_forward=confirm_before_forward,
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
async def test_concurrent_duplicate_request_has_one_delivery_owner(tmp_path: Path) -> None:
    """Two overlapping handlers with one request ID must issue one Telegram send."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["forward_text"]
    bot = BlockingBot()
    first_message = FakeMessage(bot=bot, message_id=55)
    second_message = FakeMessage(bot=bot, message_id=55)

    async def run_first() -> None:
        await handler(first_message)

    first = asyncio.create_task(run_first())
    await bot.started.wait()
    await asyncio.wait_for(handler(second_message), timeout=2)

    assert bot.attempts == 1
    assert second_message.answers == [RU_MESSAGES.request_in_progress]
    bot.release.set()
    await first
    assert len(bot.sent_messages) == 1


@pytest.mark.asyncio
async def test_forward_text_skips_legacy_fallback_request_id(tmp_path: Path) -> None:
    """A pre-upgrade local request ID must remain idempotent after the hash migration."""

    settings = _settings(tmp_path)
    bot = FakeBot()
    message = FakeMessage(bot=bot, message_id=None)
    legacy_request_id = MessageFormatter().format_legacy_request_id(
        incoming_from_message(message)  # type: ignore[arg-type]
    )
    assert legacy_request_id is not None
    request_log = RequestLog(settings.storage_path)
    lease = request_log.begin_delivery(
        request_id=legacy_request_id,
        target_chat_id=settings.forward_chat_id,
        sender_username="alice",
    )
    assert lease is not None
    request_log.mark_delivery(lease=lease, status="delivered")
    router = create_router(settings, build_service(settings))

    await _message_handlers(router)["forward_text"](message)

    assert bot.sent_messages == []
    assert message.answers == [REQUEST_ACCEPTED_MESSAGE]


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
async def test_pending_confirmation_survives_router_restart(tmp_path: Path) -> None:
    """A visible preview must remain confirmable after process/router reconstruction."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    first_handlers = _message_handlers(create_router(settings, build_service(settings)))
    bot = FakeBot()
    request = FakeMessage(bot=bot)
    await first_handlers["forward_text"](request)

    restarted_handlers = _message_handlers(create_router(settings, build_service(settings)))
    confirm = FakeMessage(text="/confirm tg-100-55", bot=bot)
    await restarted_handlers["confirm_request"](confirm)

    assert confirm.answers == [RU_MESSAGES.request_confirmed.format(request_id="tg-100-55")]
    assert len(bot.sent_messages) == 1


@pytest.mark.asyncio
async def test_pending_cancel_survives_restart_and_removes_request(tmp_path: Path) -> None:
    """Cancellation through a new store instance must persist for later processes."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    first_handlers = _message_handlers(create_router(settings, build_service(settings)))
    bot = FakeBot()
    await first_handlers["forward_text"](FakeMessage(bot=bot))

    restarted_handlers = _message_handlers(create_router(settings, build_service(settings)))
    cancel = FakeMessage(text="/cancel tg-100-55", bot=bot)
    await restarted_handlers["cancel_request"](cancel)
    assert cancel.answers == [RU_MESSAGES.request_cancelled.format(request_id="tg-100-55")]

    final_handlers = _message_handlers(create_router(settings, build_service(settings)))
    confirm = FakeMessage(text="/confirm tg-100-55", bot=bot)
    await final_handlers["confirm_request"](confirm)
    assert confirm.answers == [RU_MESSAGES.no_pending_request]
    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_forward_text_rejects_payload_over_telegram_limit(tmp_path: Path) -> None:
    """Formatting overhead must not turn a valid incoming message into an API failure."""

    settings = _settings(tmp_path)
    router = create_router(settings, build_service(settings))
    handler = _message_handlers(router)["forward_text"]
    bot = FakeBot()
    text = f"{VALID_REQUEST}\nКомментарий: {'x' * 3900}"
    assert len(text) <= 4096
    message = FakeMessage(text=text, bot=bot)

    await handler(message)

    assert message.answers == [RU_MESSAGES.request_too_long]
    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_confirmation_preview_over_telegram_limit_is_not_left_pending(tmp_path: Path) -> None:
    """An oversized preview should be rejected without leaving a confirmable request."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    router = create_router(settings, build_service(settings))
    handlers = _message_handlers(router)
    bot = FakeBot()
    text = f"{VALID_REQUEST}\nКомментарий: {'x' * 3800}"
    message = FakeMessage(text=text, bot=bot)

    await handlers["forward_text"](message)

    assert message.answers == [RU_MESSAGES.request_too_long]
    assert bot.sent_messages == []

    confirm = FakeMessage(bot=bot)
    await handlers["confirm_request"](confirm)
    assert confirm.answers == [RU_MESSAGES.no_pending_request]


@pytest.mark.asyncio
async def test_pending_confirmation_is_isolated_per_user_in_shared_chat(tmp_path: Path) -> None:
    """Another participant in a shared chat must not confirm someone else's request."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    router = create_router(settings, build_service(settings))
    handlers = _message_handlers(router)
    bot = FakeBot()

    await handlers["forward_text"](FakeMessage(user_id=10, bot=bot, chat_id=-1000))

    other_user = FakeMessage(user_id=999, bot=bot, chat_id=-1000)
    await handlers["confirm_request"](other_user)

    assert other_user.answers == [RU_MESSAGES.no_pending_request]
    assert bot.sent_messages == []

    owner = FakeMessage(user_id=10, bot=bot, chat_id=-1000)
    await handlers["confirm_request"](owner)

    assert owner.answers == [RU_MESSAGES.request_confirmed.format(request_id="tg--1000-55")]
    assert len(bot.sent_messages) == 1


@pytest.mark.asyncio
async def test_pending_confirmation_is_retained_after_delivery_failure(tmp_path: Path) -> None:
    """A failed confirmed delivery should remain available for a safe retry."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    router = create_router(settings, build_service(settings))
    handlers = _message_handlers(router)
    bot = FailOnceBot()

    await handlers["forward_text"](FakeMessage(bot=bot))

    failed_confirm = FakeMessage(bot=bot)
    with pytest.raises(RuntimeError, match="temporary delivery failure"):
        await handlers["confirm_request"](failed_confirm)

    assert failed_confirm.answers == [
        RU_MESSAGES.request_confirmation_failed_retry.format(request_id="tg-100-55")
    ]

    retry = FakeMessage(bot=bot)
    await handlers["confirm_request"](retry)

    assert retry.answers == [RU_MESSAGES.request_confirmed.format(request_id="tg-100-55")]
    assert len(bot.sent_messages) == 1


@pytest.mark.asyncio
async def test_retry_guidance_failure_does_not_hide_delivery_error(tmp_path: Path) -> None:
    """A failed guidance reply must not replace the original monitored delivery error."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    handlers = _message_handlers(create_router(settings, build_service(settings)))
    bot = FailOnceBot()
    await handlers["forward_text"](FakeMessage(bot=bot))

    with pytest.raises(RuntimeError, match="temporary delivery failure"):
        await handlers["confirm_request"](FailingAnswerMessage(bot=bot))


@pytest.mark.asyncio
async def test_confirm_rechecks_current_whitelist(tmp_path: Path) -> None:
    """Removing a user from the runtime whitelist must revoke an old pending request."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    service = build_service(settings)
    router = create_router(settings, service)
    handlers = _message_handlers(router)
    bot = FakeBot()

    await handlers["forward_text"](FakeMessage(bot=bot))
    settings.whitelist_path.write_text("999\n", encoding="utf-8")
    service.reload_whitelist(settings.whitelist_path)

    confirm = FakeMessage(text="/confirm tg-100-55", bot=bot)
    await handlers["confirm_request"](confirm)

    assert confirm.answers == [settings.messages.access_denied_unknown]
    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_confirm_rechecks_current_route_acl_after_restart(tmp_path: Path) -> None:
    """A persisted preview must not bypass a route ACL changed during restart."""

    settings = _settings_with_routes(tmp_path, confirm_before_forward=True)
    routes_path = settings.routes_path
    assert routes_path is not None
    routes_path.write_text(
        '{"routes":[{"name":"private","target_chat_id":300,"allowed_user_ids":[10]}]}',
        encoding="utf-8",
    )
    first_handlers = _message_handlers(create_router(settings, build_service(settings)))
    bot = FakeBot()
    await first_handlers["forward_text"](FakeMessage(bot=bot))

    routes_path.write_text(
        '{"routes":[{"name":"private","target_chat_id":300,"allowed_user_ids":[999]}]}',
        encoding="utf-8",
    )
    restarted_handlers = _message_handlers(create_router(settings, build_service(settings)))
    confirm = FakeMessage(text="/confirm tg-100-55", bot=bot)
    await restarted_handlers["confirm_request"](confirm)

    assert confirm.answers == [settings.messages.access_denied_unknown]
    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_expired_pending_request_cannot_be_confirmed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pending confirmations should expire even while the bot process remains alive."""

    now = [100.0]
    monkeypatch.setattr(storage_module, "time", lambda: now[0])
    settings = _settings(
        tmp_path,
        confirm_before_forward=True,
        pending_request_ttl_seconds=30,
    )
    router = create_router(settings, build_service(settings))
    handlers = _message_handlers(router)
    bot = FakeBot()

    await handlers["forward_text"](FakeMessage(bot=bot))
    now[0] += 31
    handlers = _message_handlers(create_router(settings, build_service(settings)))
    confirm = FakeMessage(text="/confirm tg-100-55", bot=bot)
    await handlers["confirm_request"](confirm)

    assert confirm.answers == [RU_MESSAGES.no_pending_request]
    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_failed_preview_does_not_replace_visible_pending_request(tmp_path: Path) -> None:
    """A preview must be delivered before its request can replace confirmation state."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    router = create_router(settings, build_service(settings))
    handlers = _message_handlers(router)
    bot = FakeBot()
    await handlers["forward_text"](FakeMessage(bot=bot, message_id=55))

    hidden_request = FailingAnswerMessage(
        text=f"{VALID_REQUEST}\nКомментарий: hidden",
        bot=bot,
        message_id=56,
    )
    with pytest.raises(RuntimeError, match="preview delivery failed"):
        await handlers["forward_text"](hidden_request)

    confirm = FakeMessage(text="/confirm", bot=bot)
    await handlers["confirm_request"](confirm)

    assert confirm.answers == [RU_MESSAGES.request_confirmed.format(request_id="tg-100-55")]
    assert len(bot.sent_messages) == 1
    assert "hidden" not in bot.sent_messages[0][1]


@pytest.mark.asyncio
async def test_failed_in_flight_request_and_newer_pending_request_are_both_retained(
    tmp_path: Path,
) -> None:
    """A delivery failure must restore A without overwriting concurrently published B."""

    settings = _settings(tmp_path, confirm_before_forward=True)
    router = create_router(settings, build_service(settings))
    handlers = _message_handlers(router)
    bot = BlockingFailOnceBot()
    await handlers["forward_text"](FakeMessage(bot=bot, message_id=55))

    async def confirm_first_request() -> None:
        await handlers["confirm_request"](
            FakeMessage(text="/confirm tg-100-55", bot=bot, message_id=100)
        )

    first_confirm = asyncio.create_task(confirm_first_request())
    await bot.started.wait()
    await handlers["forward_text"](
        FakeMessage(
            text=f"{VALID_REQUEST}\nКомментарий: newer",
            bot=bot,
            message_id=56,
        )
    )
    bot.release.set()

    with pytest.raises(RuntimeError, match="temporary delivery failure"):
        await first_confirm

    retry_first = FakeMessage(text="/confirm tg-100-55", bot=bot, message_id=101)
    await handlers["confirm_request"](retry_first)
    confirm_newer = FakeMessage(text="/confirm tg-100-56", bot=bot, message_id=102)
    await handlers["confirm_request"](confirm_newer)

    assert retry_first.answers == [RU_MESSAGES.request_confirmed.format(request_id="tg-100-55")]
    assert confirm_newer.answers == [RU_MESSAGES.request_confirmed.format(request_id="tg-100-56")]
    assert len(bot.sent_messages) == 2
    assert "newer" not in bot.sent_messages[0][1]
    assert "newer" in bot.sent_messages[1][1]


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
    message = FakeMessage(username="mallory", user_id=999, bot=bot)

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
