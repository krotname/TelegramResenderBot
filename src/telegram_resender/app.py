"""Aiogram application factory and Telegram handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from telegram_resender import __version__
from telegram_resender.formatting import MessageFormatter
from telegram_resender.models import IncomingMessage, UserProfile
from telegram_resender.service import ResenderService
from telegram_resender.settings import Settings
from telegram_resender.whitelist import Whitelist

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PendingRequest:
    """Forwarding payload waiting for explicit user confirmation."""

    request_id: str
    forward_text: str


def incoming_from_message(message: Message) -> IncomingMessage:
    """Convert an aiogram message into the SDK-free domain model."""

    user = message.from_user
    return IncomingMessage(
        chat_id=message.chat.id,
        text=message.text or "",
        user=UserProfile(
            username=user.username if user else None,
            first_name=user.first_name if user else None,
            last_name=user.last_name if user else None,
        ),
        message_id=message.message_id,
        submitted_at=message.date,
    )


def build_service(settings: Settings) -> ResenderService:
    """Build the forwarding service from runtime settings."""

    whitelist = Whitelist.from_file(settings.whitelist_path)
    messages = settings.messages
    return ResenderService(
        whitelist=whitelist,
        formatter=MessageFormatter(),
        request_accepted_message=messages.request_accepted,
        access_denied_message=messages.access_denied_unknown,
        missing_username_message=messages.access_denied_missing_username,
        invalid_request_message=messages.invalid_request,
        missing_fields_message=messages.missing_fields,
        locale=settings.locale,
    )


def create_router(settings: Settings, service: ResenderService) -> Router:
    """Create Telegram handlers with dependencies injected for testing."""

    router = Router(name="telegram-resender")
    messages = settings.messages
    pending_requests: dict[int, PendingRequest] = {}

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        await message.answer(messages.start)

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(messages.help)

    @router.message(Command("avto"))
    async def car_mode(message: Message) -> None:
        await message.answer(messages.template)

    @router.message(Command("template"))
    async def template(message: Message) -> None:
        await message.answer(messages.template)

    @router.message(Command("whoami"))
    async def whoami(message: Message) -> None:
        await message.answer(
            messages.whoami.format(
                user_id=_telegram_user_id(message) or "unknown",
                chat_id=message.chat.id,
            )
        )

    @router.message(Command("admin_status"))
    async def admin_status(message: Message) -> None:
        if not _is_admin(message, settings.admin_ids):
            await message.answer(messages.admin_access_denied)
            return
        await message.answer(
            messages.admin_status.format(
                version=__version__,
                locale=settings.locale,
                forward_chat_id=settings.forward_chat_id,
                whitelist_count=service.whitelist_count,
                admin_count=len(settings.admin_ids),
                confirm_before_forward=settings.confirm_before_forward,
            )
        )

    @router.message(Command("whitelist_count"))
    async def whitelist_count(message: Message) -> None:
        if not _is_admin(message, settings.admin_ids):
            await message.answer(messages.admin_access_denied)
            return
        await message.answer(messages.whitelist_count.format(count=service.whitelist_count))

    @router.message(Command("reload_whitelist"))
    async def reload_whitelist(message: Message) -> None:
        if not _is_admin(message, settings.admin_ids):
            await message.answer(messages.admin_access_denied)
            return
        try:
            count = service.reload_whitelist(settings.whitelist_path)
        except (OSError, ValueError) as exc:
            LOGGER.warning("Failed to reload whitelist: %s", exc)
            await message.answer(messages.whitelist_reload_failed.format(error=exc))
            return
        LOGGER.info("Whitelist reloaded by admin")
        await message.answer(messages.whitelist_reloaded.format(count=count))

    @router.message(Command("confirm"))
    async def confirm_request(message: Message) -> None:
        pending = pending_requests.pop(message.chat.id, None)
        if pending is None:
            await message.answer(messages.no_pending_request)
            return
        bot = message.bot
        if bot is None:
            msg = "Telegram message is not bound to a bot"
            raise RuntimeError(msg)
        await bot.send_message(settings.forward_chat_id, pending.forward_text)
        LOGGER.info("Forwarded confirmed request from Telegram user")
        await message.answer(messages.request_confirmed.format(request_id=pending.request_id))

    @router.message(Command("cancel"))
    async def cancel_request(message: Message) -> None:
        pending = pending_requests.pop(message.chat.id, None)
        if pending is None:
            await message.answer(messages.no_pending_request)
            return
        await message.answer(messages.request_cancelled.format(request_id=pending.request_id))

    @router.message(F.text)
    async def forward_text(message: Message) -> None:
        decision = service.handle_text(incoming_from_message(message))
        if decision.should_forward and decision.forward_text is not None:
            if settings.confirm_before_forward:
                if decision.request_id is None:
                    msg = "Forwarding decision is missing request_id"
                    raise RuntimeError(msg)
                pending_requests[message.chat.id] = PendingRequest(
                    request_id=decision.request_id,
                    forward_text=decision.forward_text,
                )
                await message.answer(
                    messages.confirmation_prompt.format(
                        request_id=decision.request_id,
                        preview=decision.forward_text,
                    )
                )
                return
            bot = message.bot
            if bot is None:
                msg = "Telegram message is not bound to a bot"
                raise RuntimeError(msg)
            await bot.send_message(settings.forward_chat_id, decision.forward_text)
            LOGGER.info("Forwarded message from Telegram user")
        else:
            LOGGER.info("Rejected message: %s", decision.reason)
        await message.answer(decision.response_text)

    @router.message()
    async def unsupported_message(message: Message) -> None:
        await message.answer(messages.unsupported_message)

    return router


def _telegram_user_id(message: Message) -> int | None:
    user = message.from_user
    return user.id if user else None


def _is_admin(message: Message, admin_ids: frozenset[int]) -> bool:
    user_id = _telegram_user_id(message)
    return user_id in admin_ids if user_id is not None else False


def create_dispatcher(settings: Settings, service: ResenderService) -> Dispatcher:
    """Create a dispatcher for polling or tests."""

    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(settings, service))
    return dispatcher


async def run_polling(settings: Settings | None = None) -> None:  # pragma: no cover
    """Run the bot in long polling mode."""

    loaded_settings = settings or Settings()  # type: ignore[call-arg]
    logging.basicConfig(
        level=loaded_settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    service = build_service(loaded_settings)
    dispatcher = create_dispatcher(loaded_settings, service)
    bot = Bot(token=loaded_settings.bot_token)
    LOGGER.info("Starting Telegram Resender polling")
    await dispatcher.start_polling(
        bot,
        polling_timeout=loaded_settings.polling_timeout,
        allowed_updates=dispatcher.resolve_used_update_types(),
    )
