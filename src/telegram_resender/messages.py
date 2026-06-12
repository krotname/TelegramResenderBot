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
    "Request template:\n"
    "Building: \n"
    "Arrival date and time: \n"
    "Vehicle: \n"
    "License plate: \n"
    "Comment: "
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
    missing_fields: str
    confirmation_prompt: str
    request_confirmed: str
    request_cancelled: str
    no_pending_request: str

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
        "Этот бот закрытый. Попросите администратора добавить ваш Telegram username "
        "в белый список."
    ),
    access_denied_missing_username=(
        "У вас не задан Telegram username. Создайте username в настройках Telegram "
        "или попросите администратора включить доступ по chat id: {chat_id}."
    ),
    unsupported_message=(
        "Пока я принимаю только текстовые заявки. Отправьте текст по шаблону из /template."
    ),
    invalid_request=(
        "Заявка выглядит неполной. Отправьте объект, время прибытия, модель автомобиля "
        "и госномер. Шаблон доступен по команде /template."
    ),
    missing_fields=(
        "Заявка неполная. Заполните обязательные поля: {fields}. "
        "Шаблон доступен по команде /template."
    ),
    confirmation_prompt=(
        "Проверьте заявку {request_id}:\n\n{preview}\n\n"
        "Отправьте /confirm, чтобы передать ее администратору, или /cancel, чтобы отменить."
    ),
    request_confirmed="Заявка {request_id} подтверждена и передана администратору.",
    request_cancelled="Заявка {request_id} отменена.",
    no_pending_request="Нет заявки, ожидающей подтверждения.",
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
        "This bot is private. Ask an administrator to add your Telegram username."
    ),
    access_denied_missing_username=(
        "Your Telegram username is not set. Create one in Telegram settings or ask "
        "the administrator to allow your chat id: {chat_id}."
    ),
    unsupported_message=(
        "I can only accept text requests for now. Send a text message using /template."
    ),
    invalid_request=(
        "The request looks incomplete. Send the building, arrival time, vehicle model, "
        "and license plate. Use /template for the expected format."
    ),
    missing_fields=(
        "The request is incomplete. Fill these required fields: {fields}. "
        "Use /template for the expected format."
    ),
    confirmation_prompt=(
        "Review request {request_id}:\n\n{preview}\n\n"
        "Send /confirm to forward it to the administrator or /cancel to discard it."
    ),
    request_confirmed="Request {request_id} has been confirmed and sent to the administrator.",
    request_cancelled="Request {request_id} has been cancelled.",
    no_pending_request="There is no request waiting for confirmation.",
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
