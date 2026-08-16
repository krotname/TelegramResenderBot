"""Aiogram application factory and Telegram handlers."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from telegram_resender import __version__
from telegram_resender.delivery import send_with_retry
from telegram_resender.formatting import MessageFormatter
from telegram_resender.models import IncomingMessage, UserProfile
from telegram_resender.requests import parse_request
from telegram_resender.routes import default_route, load_routes
from telegram_resender.service import ResenderService
from telegram_resender.settings import Settings
from telegram_resender.storage import (
    DeliveryInProgressError,
    DeliveryLease,
    PendingRequestKey,
    PendingRequestStore,
    RequestLog,
)
from telegram_resender.telegram_limits import fits_telegram_message
from telegram_resender.whitelist import Whitelist

LOGGER = logging.getLogger(__name__)


class JsonLogFormatter(logging.Formatter):
    """Small JSON formatter for production logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def incoming_from_message(message: Message) -> IncomingMessage:
    """Convert an aiogram message into the SDK-free domain model."""

    user = message.from_user
    return IncomingMessage(
        chat_id=message.chat.id,
        text=message.text or "",
        user=UserProfile(
            id=user.id if user else None,
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
    routes = (
        load_routes(settings.routes_path)
        if settings.routes_path is not None
        else (default_route(settings.forward_chat_id),)
    )
    messages = settings.messages
    return ResenderService(
        whitelist=whitelist,
        formatter=MessageFormatter(),
        request_accepted_message=messages.request_accepted,
        access_denied_message=messages.access_denied_unknown,
        missing_username_message=messages.access_denied_missing_username,
        invalid_request_message=messages.invalid_request,
        missing_fields_message=messages.missing_fields,
        no_route_matched_message=messages.no_route_matched,
        locale=settings.locale,
        routes=routes,
    )


def create_router(settings: Settings, service: ResenderService) -> Router:
    """Create Telegram handlers with dependencies injected for testing."""

    router = Router(name="telegram-resender")
    messages = settings.messages
    request_log = RequestLog(
        settings.storage_path,
        lease_seconds=settings.delivery_lease_seconds,
    )
    pending_requests = PendingRequestStore(
        settings.storage_path,
        ttl_seconds=settings.pending_request_ttl_seconds,
        claim_seconds=settings.delivery_lease_seconds,
    )

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
        pending_key = _pending_request_key(message)
        pending = pending_requests.claim(
            pending_key,
            request_id=_command_request_id(message, command="confirm"),
        )
        if pending is None:
            await message.answer(messages.no_pending_request)
            return
        if not service.routes_still_authorize(
            user_id=pending.sender_user_id,
            username=pending.sender_username,
            route_match_text=pending.route_match_text,
            target_chat_ids=tuple(chat_id for chat_id, _ in pending.forward_text_by_chat_id),
        ):
            if service.is_authorized(pending.sender_user_id):
                pending_requests.complete(pending_key, pending)
            else:
                pending_requests.discard_all(pending_key)
            await message.answer(_access_denied_text(message, settings))
            return
        try:
            bot = message.bot
            if bot is None:
                msg = "Telegram message is not bound to a bot"
                raise RuntimeError(msg)
            await _deliver_payloads(
                bot=bot,
                request_log=request_log,
                request_id=pending.request_id,
                request_id_aliases=pending.request_id_aliases,
                forward_text_by_chat_id=pending.forward_text_by_chat_id,
                sender_username=pending.sender_username,
                settings=settings,
                pending_keepalive=lambda wait_seconds: pending_requests.renew(
                    pending_key,
                    pending,
                    wait_seconds=wait_seconds,
                ),
            )
        except DeliveryInProgressError:
            restored = pending_requests.release(pending_key, pending)
            await message.answer(
                messages.request_in_progress
                if restored
                else messages.request_confirmation_failed_expired.format(
                    request_id=pending.request_id
                )
            )
            return
        except Exception:
            LOGGER.exception("Confirmed request delivery failed")
            restored = False
            if service.is_authorized(pending.sender_user_id):
                try:
                    restored = pending_requests.release(pending_key, pending)
                except Exception:
                    LOGGER.exception("Failed to release pending request after delivery error")
            guidance = (
                messages.request_confirmation_failed_retry.format(request_id=pending.request_id)
                if restored
                else messages.request_confirmation_failed_expired.format(
                    request_id=pending.request_id
                )
            )
            try:
                await message.answer(guidance)
            except Exception:
                LOGGER.exception("Failed to send confirmation retry guidance")
            raise
        if not pending_requests.complete(pending_key, pending):
            LOGGER.warning(
                "Pending request ownership changed before completion: %s",
                pending.request_id,
            )
        LOGGER.info("Forwarded confirmed request from Telegram user")
        await message.answer(messages.request_confirmed.format(request_id=pending.request_id))

    @router.message(Command("cancel"))
    async def cancel_request(message: Message) -> None:
        pending = pending_requests.cancel(
            _pending_request_key(message),
            request_id=_command_request_id(message, command="cancel"),
        )
        if pending is None:
            await message.answer(messages.no_pending_request)
            return
        await message.answer(messages.request_cancelled.format(request_id=pending.request_id))

    @router.message(F.text)
    async def forward_text(message: Message) -> None:
        incoming = incoming_from_message(message)
        decision = service.handle_text(incoming)
        if decision.should_forward and decision.forward_text is not None:
            forward_payloads = decision.forward_payloads or tuple(
                (
                    chat_id,
                    service.render_forward_text_for_target(chat_id, decision.forward_text),
                )
                for chat_id in decision.target_chat_ids
            )
            if any(not fits_telegram_message(text) for _, text in forward_payloads):
                await message.answer(messages.request_too_long)
                return
            if settings.confirm_before_forward:
                if decision.request_id is None:
                    msg = "Forwarding decision is missing request_id"
                    raise RuntimeError(msg)
                confirmation_text = messages.confirmation_prompt.format(
                    request_id=decision.request_id,
                    preview=decision.forward_text,
                )
                if not fits_telegram_message(confirmation_text):
                    await message.answer(messages.request_too_long)
                    return
                await message.answer(confirmation_text)
                pending_requests.publish(
                    _pending_request_key(message),
                    request_id=decision.request_id,
                    request_id_aliases=decision.request_id_aliases,
                    forward_text_by_chat_id=forward_payloads,
                    sender_user_id=incoming.user.id,
                    sender_username=incoming.user.username,
                    route_match_text=parse_request(incoming.text).fields["building"],
                )
                return
            bot = message.bot
            if bot is None:
                msg = "Telegram message is not bound to a bot"
                raise RuntimeError(msg)
            if decision.request_id is None:
                msg = "Forwarding decision is missing request_id"
                raise RuntimeError(msg)
            try:
                await _deliver_payloads(
                    bot=bot,
                    request_log=request_log,
                    request_id=decision.request_id,
                    request_id_aliases=decision.request_id_aliases,
                    forward_text_by_chat_id=forward_payloads,
                    sender_username=incoming.user.username,
                    settings=settings,
                )
            except DeliveryInProgressError:
                await message.answer(messages.request_in_progress)
                return
            except Exception:
                LOGGER.exception("Request delivery failed")
                try:
                    await message.answer(
                        messages.request_delivery_failed.format(request_id=decision.request_id)
                    )
                except Exception:
                    LOGGER.exception("Failed to send delivery failure notice")
                raise
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


def _pending_request_key(message: Message) -> PendingRequestKey:
    """Keep confirmations isolated per user, including inside shared chats."""

    return message.chat.id, _telegram_user_id(message)


def _command_request_id(message: Message, *, command: str) -> str | None:
    text = (message.text or "").strip()
    if not text:
        return None
    command_parts = text.split(maxsplit=1)
    command_token = command_parts[0]
    bare_command = command_token.partition("@")[0].casefold()
    if bare_command != f"/{command}" or len(command_parts) == 1:
        return None
    return command_parts[1].strip() or None


def _access_denied_text(message: Message, settings: Settings) -> str:
    user_id = _telegram_user_id(message)
    if user_id is None:
        return settings.messages.access_denied_missing_username.format(chat_id=message.chat.id)
    return settings.messages.access_denied_unknown


def _is_admin(message: Message, admin_ids: frozenset[int]) -> bool:
    user_id = _telegram_user_id(message)
    return user_id in admin_ids if user_id is not None else False


async def _deliver_payloads(
    *,
    bot: Bot,
    request_log: RequestLog,
    request_id: str,
    request_id_aliases: tuple[str, ...],
    forward_text_by_chat_id: tuple[tuple[int, str], ...],
    sender_username: str | None,
    settings: Settings,
    pending_keepalive: Callable[[float], bool] | None = None,
) -> None:
    for chat_id, forward_text in forward_text_by_chat_id:
        lease = request_log.begin_delivery(
            request_id=request_id,
            target_chat_id=chat_id,
            sender_username=sender_username,
            request_id_aliases=request_id_aliases,
        )
        if lease is None:
            LOGGER.info("Skipped already delivered request %s to %s", request_id, chat_id)
            continue
        owned_lease: DeliveryLease = lease

        def renew_ownership(
            wait_seconds: float,
            delivery_lease: DeliveryLease = owned_lease,
        ) -> None:
            if not request_log.renew_delivery(delivery_lease, wait_seconds=wait_seconds):
                msg = "Telegram delivery ownership was superseded before retry"
                raise RuntimeError(msg)
            if pending_keepalive is not None and not pending_keepalive(wait_seconds):
                msg = "Pending confirmation ownership was superseded before retry"
                raise RuntimeError(msg)

        try:
            renew_ownership(0.0)
            await send_with_retry(
                bot.send_message,
                chat_id=chat_id,
                text=forward_text,
                max_attempts=settings.delivery_max_attempts,
                backoff_seconds=settings.delivery_retry_backoff,
                before_retry_wait=renew_ownership,
            )
        except Exception as exc:
            try:
                marked = request_log.mark_delivery(
                    lease=lease,
                    status="failed",
                    error=str(exc),
                )
                if not marked:
                    LOGGER.warning("Delivery failure lease was already superseded")
            except Exception:
                LOGGER.exception("Failed to persist Telegram delivery failure")
            raise
        if not request_log.mark_delivery(lease=lease, status="delivered"):
            msg = "Telegram delivery completed after its ownership lease was superseded"
            raise RuntimeError(msg)


def create_dispatcher(settings: Settings, service: ResenderService) -> Dispatcher:
    """Create a dispatcher for polling or tests."""

    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(settings, service))
    return dispatcher


async def run_polling(settings: Settings | None = None) -> None:  # pragma: no cover
    """Run the bot in long polling mode."""

    loaded_settings = settings or Settings()  # type: ignore[call-arg]
    configure_logging(loaded_settings)
    service = build_service(loaded_settings)
    dispatcher = create_dispatcher(loaded_settings, service)
    bot = Bot(token=loaded_settings.bot_token)
    LOGGER.info("Starting Telegram Resender polling")
    await dispatcher.start_polling(
        bot,
        polling_timeout=loaded_settings.polling_timeout,
        allowed_updates=dispatcher.resolve_used_update_types(),
    )


def configure_logging(settings: Settings) -> None:
    """Configure process logging from runtime settings."""

    handler = logging.StreamHandler()
    if settings.log_format == "JSON":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=settings.log_level, handlers=[handler], force=True)
