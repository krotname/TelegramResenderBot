"""Default user-facing bot messages."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

Locale = Literal["ru", "en"]

REQUEST_TEMPLATE_RU = (
    "Шаблон заявки:\n"
    "Объект/здание: \n"
    "Дата и время прибытия: \n"
    "Автомобиль: \n"
    "Госномер: \n"
    "Комментарий: "
)

REQUEST_TEMPLATE_EN = (
    "Request template:\nBuilding: \nArrival date and time: \nVehicle: \nLicense plate: \nComment: "
)


@dataclass(frozen=True, slots=True)
class MessageCatalog:
    """Localized messages shown to Telegram users."""

    start: str
    help: str
    template: str
    request_accepted: str
    access_denied_unknown: str
    access_denied_missing_username: str
    unsupported_message: str
    invalid_request: str
    request_too_long: str
    request_in_progress: str
    missing_fields: str
    no_route_matched: str
    confirmation_prompt: str
    request_confirmed: str
    request_cancelled: str
    request_confirmation_failed_retry: str
    request_confirmation_failed_expired: str
    request_delivery_failed: str
    no_pending_request: str
    admin_access_denied: str
    admin_status: str
    whitelist_count: str
    whitelist_reloaded: str
    whitelist_reload_failed: str
    whoami: str

    def with_overrides(
        self,
        *,
        request_accepted: str | None = None,
        access_denied_unknown: str | None = None,
    ) -> MessageCatalog:
        """Apply backward-compatible environment overrides."""

        return replace(
            self,
            request_accepted=request_accepted or self.request_accepted,
            access_denied_unknown=access_denied_unknown or self.access_denied_unknown,
        )


RU_MESSAGES = MessageCatalog(
    start=(
        "Здравствуйте. Отправьте текстовую заявку на пропуск автомобиля. "
        "Используйте /template, чтобы получить шаблон."
    ),
    help=(
        "Бот принимает только текстовые заявки от пользователей из белого списка. "
        "Если доступ не работает, напишите администратору."
    ),
    template=REQUEST_TEMPLATE_RU,
    request_accepted="Заявка принята и передана администратору.",
    access_denied_unknown=(
        "Этот бот закрытый. Попросите администратора добавить ваш числовой Telegram user ID "
        "в белый список. Узнать ID можно командой /whoami."
    ),
    access_denied_missing_username=(
        "Не удалось определить Telegram user ID отправителя. Обратитесь к администратору "
        "и сообщите для диагностики chat id: {chat_id}."
    ),
    unsupported_message=(
        "Пока я принимаю только текстовые заявки. Отправьте текст по шаблону из /template."
    ),
    invalid_request=(
        "Заявка выглядит неполной. Отправьте объект, время прибытия, модель автомобиля "
        "и госномер. Шаблон доступен по команде /template."
    ),
    request_too_long=(
        "Заявка слишком длинная для пересылки в Telegram. Сократите комментарий или другие "
        "поля и отправьте заявку повторно."
    ),
    request_in_progress=(
        "Эта заявка уже передается администратору. Дождитесь результата и не отправляйте "
        "ее повторно."
    ),
    missing_fields=(
        "Заявка неполная. Заполните обязательные поля: {fields}. "
        "Шаблон доступен по команде /template."
    ),
    no_route_matched="Заявка заполнена, но для нее не найден активный маршрут пересылки.",
    confirmation_prompt=(
        "Проверьте заявку {request_id}:\n\n{preview}\n\n"
        "Отправьте /confirm {request_id}, чтобы передать ее администратору, "
        "или /cancel {request_id}, чтобы отменить. Команды без ID применяются к последней заявке."
    ),
    request_confirmed="Заявка {request_id} подтверждена и передана администратору.",
    request_cancelled="Заявка {request_id} отменена.",
    request_confirmation_failed_retry=(
        "Не удалось передать заявку {request_id}. Она сохранена: повторите "
        "/confirm {request_id} позже."
    ),
    request_confirmation_failed_expired=(
        "Не удалось передать заявку {request_id}, а срок ее подтверждения уже истек. "
        "Отправьте заявку заново."
    ),
    request_delivery_failed=(
        "Не удалось подтвердить передачу заявки {request_id}. Часть адресатов могла ее уже "
        "получить, поэтому не отправляйте заявку повторно: сообщите администратору номер "
        "{request_id}."
    ),
    no_pending_request="Нет заявки, ожидающей подтверждения.",
    admin_access_denied="Эта команда доступна только администратору.",
    admin_status=(
        "Статус бота:\n"
        "Версия: {version}\n"
        "Locale: {locale}\n"
        "Целевой чат: {forward_chat_id}\n"
        "Whitelist users: {whitelist_count}\n"
        "Admin users: {admin_count}\n"
        "Confirm before forward: {confirm_before_forward}"
    ),
    whitelist_count="В белом списке пользователей: {count}.",
    whitelist_reloaded="Белый список перезагружен. Пользователей: {count}.",
    whitelist_reload_failed="Не удалось перезагрузить белый список: {error}",
    whoami="Ваш Telegram user id: {user_id}\nChat id: {chat_id}",
)

EN_MESSAGES = MessageCatalog(
    start=(
        "Hello. Send a vehicle pass request as a text message. "
        "Use /template to get the expected format."
    ),
    help=(
        "The bot accepts text requests only from whitelisted users. "
        "If access does not work, contact the administrator."
    ),
    template=REQUEST_TEMPLATE_EN,
    request_accepted="Your request has been accepted and sent to the administrator.",
    access_denied_unknown=(
        "This bot is private. Ask an administrator to add your numeric Telegram user ID "
        "to the whitelist. Use /whoami to discover the ID."
    ),
    access_denied_missing_username=(
        "The sender's Telegram user ID could not be determined. Contact an administrator "
        "and provide this chat ID for diagnostics: {chat_id}."
    ),
    unsupported_message=(
        "I can only accept text requests for now. Send a text message using /template."
    ),
    invalid_request=(
        "The request looks incomplete. Send the building, arrival time, vehicle model, "
        "and license plate. Use /template for the expected format."
    ),
    request_too_long=(
        "The request is too long to forward through Telegram. Shorten the comment or other "
        "fields and send it again."
    ),
    request_in_progress=(
        "This request is already being delivered. Wait for the result instead of sending it again."
    ),
    missing_fields=(
        "The request is incomplete. Fill these required fields: {fields}. "
        "Use /template for the expected format."
    ),
    no_route_matched="The request is complete, but no active forwarding route matched it.",
    confirmation_prompt=(
        "Review request {request_id}:\n\n{preview}\n\n"
        "Send /confirm {request_id} to forward it to the administrator or "
        "/cancel {request_id} to discard it. Commands without an ID apply to the latest request."
    ),
    request_confirmed="Request {request_id} has been confirmed and sent to the administrator.",
    request_cancelled="Request {request_id} has been cancelled.",
    request_confirmation_failed_retry=(
        "Request {request_id} could not be delivered but remains saved. "
        "Retry /confirm {request_id} later."
    ),
    request_confirmation_failed_expired=(
        "Request {request_id} could not be delivered and its confirmation window has expired. "
        "Send the request again."
    ),
    request_delivery_failed=(
        "Delivery of request {request_id} could not be confirmed. Some recipients may already "
        "have it, so do not send the request again: report id {request_id} to an administrator."
    ),
    no_pending_request="There is no request waiting for confirmation.",
    admin_access_denied="This command is available to administrators only.",
    admin_status=(
        "Bot status:\n"
        "Version: {version}\n"
        "Locale: {locale}\n"
        "Forward chat: {forward_chat_id}\n"
        "Whitelist users: {whitelist_count}\n"
        "Admin users: {admin_count}\n"
        "Confirm before forward: {confirm_before_forward}"
    ),
    whitelist_count="Whitelisted users: {count}.",
    whitelist_reloaded="Whitelist reloaded. Users: {count}.",
    whitelist_reload_failed="Failed to reload whitelist: {error}",
    whoami="Your Telegram user id: {user_id}\nChat id: {chat_id}",
)

CATALOGS: dict[Locale, MessageCatalog] = {
    "ru": RU_MESSAGES,
    "en": EN_MESSAGES,
}


def message_catalog(locale: Locale) -> MessageCatalog:
    """Return messages for the requested locale."""

    return CATALOGS[locale]


# Backward-compatible module constants used by older tests/imports.
START_MESSAGE = RU_MESSAGES.start
HELP_MESSAGE = RU_MESSAGES.help
CAR_MODE_MESSAGE = RU_MESSAGES.template
REQUEST_ACCEPTED_MESSAGE = RU_MESSAGES.request_accepted
ACCESS_DENIED_MESSAGE = RU_MESSAGES.access_denied_unknown
