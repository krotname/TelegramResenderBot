"""Unit tests for access-control and forwarding rules."""

from telegram_resender.formatting import MessageFormatter
from telegram_resender.messages import RU_MESSAGES
from telegram_resender.models import IncomingMessage, UserProfile
from telegram_resender.requests import parse_request
from telegram_resender.service import ResenderService
from telegram_resender.whitelist import Whitelist

VALID_REQUEST = (
    "Объект/здание: Башня А\n"
    "Дата и время прибытия: 12.06.2026 10:30\n"
    "Автомобиль: Ford Focus\n"
    "Госномер: А123ВС"
)


def test_service_forwards_only_whitelisted() -> None:
    """A missing or unknown username should not be forwarded."""

    service = ResenderService(
        whitelist=Whitelist(["alice", "bob"]),
        formatter=MessageFormatter(),
        request_accepted_message="ok",
        access_denied_message="deny",
        missing_username_message=RU_MESSAGES.access_denied_missing_username,
        invalid_request_message=RU_MESSAGES.invalid_request,
        missing_fields_message=RU_MESSAGES.missing_fields,
        locale="ru",
    )

    approved = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text=VALID_REQUEST,
            user=UserProfile(username="Alice"),
        )
    )
    denied_unknown = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text=VALID_REQUEST,
            user=UserProfile(username="Charlie"),
        )
    )
    denied_missing = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text=VALID_REQUEST,
            user=UserProfile(username=None),
        )
    )
    invalid_request = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text="hi",
            user=UserProfile(username="Alice"),
        )
    )

    assert approved.should_forward is True
    assert approved.forward_text is not None
    assert approved.response_text == "ok"
    assert approved.reason == "allowed_username"
    assert approved.request_id is not None

    assert denied_unknown.should_forward is False
    assert denied_unknown.response_text == "deny"
    assert denied_unknown.reason == "unknown_username"

    assert denied_missing.should_forward is False
    assert "chat id: 1" in denied_missing.response_text
    assert denied_missing.reason == "missing_username"

    assert invalid_request.should_forward is False
    assert invalid_request.response_text == RU_MESSAGES.invalid_request
    assert invalid_request.reason == "invalid_request"


def test_service_reports_missing_template_fields() -> None:
    """A labeled but incomplete request should name the missing fields."""

    service = ResenderService(
        whitelist=Whitelist(["alice"]),
        formatter=MessageFormatter(),
        request_accepted_message="ok",
        access_denied_message="deny",
        missing_username_message=RU_MESSAGES.access_denied_missing_username,
        invalid_request_message=RU_MESSAGES.invalid_request,
        missing_fields_message=RU_MESSAGES.missing_fields,
        locale="ru",
    )

    decision = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text="Объект/здание: Башня А\nАвтомобиль: Ford Focus",
            user=UserProfile(username="alice"),
        )
    )

    assert decision.should_forward is False
    assert "дата и время прибытия" in decision.response_text
    assert "госномер" in decision.response_text


def test_parse_request_supports_english_template() -> None:
    """The request parser should understand English labels as well."""

    parsed = parse_request(
        "Building: Tower A\n"
        "Arrival date and time: 2026-06-12 10:30\n"
        "Vehicle: Ford Focus\n"
        "License plate: A123BC"
    )

    assert parsed.is_complete is True
    assert parsed.fields["building"] == "Tower A"
