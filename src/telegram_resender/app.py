"""Aiogram application factory and Telegram handlers."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from telegram_resender.formatting import MessageFormatter
from telegram_resender.messages import CAR_MODE_MESSAGE, HELP_MESSAGE, START_MESSAGE
from telegram_resender.models import IncomingMessage, UserProfile
from telegram_resender.service import ResenderService
from telegram_resender.settings import Settings
from telegram_resender.whitelist import Whitelist

LOGGER = logging.getLogger(__name__)


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
    )


def build_service(settings: Settings) -> ResenderService:
    """Build the forwarding service from runtime settings."""

    whitelist = Whitelist.from_file(settings.whitelist_path)
    return ResenderService(
        whitelist=whitelist,
        formatter=MessageFormatter(),
        request_accepted_message=settings.request_accepted_message,
        access_denied_message=settings.access_denied_message,
    )


def create_router(settings: Settings, service: ResenderService) -> Router:
    """Create Telegram handlers with dependencies injected for testing."""

    router = Router(name="telegram-resender")

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        await message.answer(START_MESSAGE)

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(HELP_MESSAGE)

    @router.message(Command("avto"))
    async def car_mode(message: Message) -> None:
        await message.answer(CAR_MODE_MESSAGE)

    @router.message(F.text)
    async def forward_text(message: Message) -> None:
        decision = service.handle_text(incoming_from_message(message))
        if decision.should_forward and decision.forward_text is not None:
            await message.bot.send_message(settings.forward_chat_id, decision.forward_text)
            LOGGER.info("Forwarded message from Telegram user")
        else:
            LOGGER.info("Rejected message: %s", decision.reason)
        await message.answer(decision.response_text)

    return router


def create_dispatcher(settings: Settings, service: ResenderService) -> Dispatcher:
    """Create a dispatcher for polling or tests."""

    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(settings, service))
    return dispatcher


async def run_polling(settings: Settings | None = None) -> None:  # pragma: no cover
    """Run the bot in long polling mode."""

    loaded_settings = settings or Settings()
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
