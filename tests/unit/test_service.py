"""Unit tests for access-control and forwarding rules."""

from telegram_resender.formatting import MessageFormatter
from telegram_resender.messages import RU_MESSAGES
from telegram_resender.models import IncomingMessage, UserProfile
from telegram_resender.requests import parse_request
from telegram_resender.routes import RouteRule, default_route
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
        whitelist=Whitelist([10, 20]),
        formatter=MessageFormatter(),
        request_accepted_message="ok",
        access_denied_message="deny",
        missing_username_message=RU_MESSAGES.access_denied_missing_username,
        invalid_request_message=RU_MESSAGES.invalid_request,
        missing_fields_message=RU_MESSAGES.missing_fields,
        no_route_matched_message=RU_MESSAGES.no_route_matched,
        locale="ru",
        routes=(default_route(200),),
    )

    approved = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text=VALID_REQUEST,
            user=UserProfile(id=10, username="Alice"),
        )
    )
    denied_unknown = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text=VALID_REQUEST,
            user=UserProfile(id=30, username="Charlie"),
        )
    )
    denied_missing = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text=VALID_REQUEST,
            user=UserProfile(id=None, username=None),
        )
    )
    invalid_request = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text="hi",
            user=UserProfile(id=10, username="Alice"),
        )
    )

    assert approved.should_forward is True
    assert approved.forward_text is not None
    assert approved.response_text == "ok"
    assert approved.reason == "allowed_user_id"
    assert approved.request_id is not None

    assert denied_unknown.should_forward is False
    assert denied_unknown.response_text == "deny"
    assert denied_unknown.reason == "unknown_user_id"

    assert denied_missing.should_forward is False
    assert "chat id: 1" in denied_missing.response_text
    assert denied_missing.reason == "missing_user_id"

    assert invalid_request.should_forward is False
    assert invalid_request.response_text == RU_MESSAGES.invalid_request
    assert invalid_request.reason == "invalid_request"


def test_service_authorizes_by_user_id_not_username() -> None:
    """Mutable usernames must not grant or remove whitelist access."""

    service = ResenderService(
        whitelist=Whitelist([10]),
        formatter=MessageFormatter(),
        request_accepted_message="ok",
        access_denied_message="deny",
        missing_username_message=RU_MESSAGES.access_denied_missing_username,
        invalid_request_message=RU_MESSAGES.invalid_request,
        missing_fields_message=RU_MESSAGES.missing_fields,
        no_route_matched_message=RU_MESSAGES.no_route_matched,
        locale="ru",
        routes=(default_route(200),),
    )

    changed_username = service.handle_text(
        IncomingMessage(chat_id=1, text=VALID_REQUEST, user=UserProfile(id=10, username="mallory"))
    )
    reclaimed_username = service.handle_text(
        IncomingMessage(chat_id=1, text=VALID_REQUEST, user=UserProfile(id=30, username="alice"))
    )

    assert changed_username.should_forward is True
    assert changed_username.reason == "allowed_user_id"
    assert reclaimed_username.should_forward is False
    assert reclaimed_username.reason == "unknown_user_id"


def test_service_reports_missing_template_fields() -> None:
    """A labeled but incomplete request should name the missing fields."""

    service = ResenderService(
        whitelist=Whitelist([10]),
        formatter=MessageFormatter(),
        request_accepted_message="ok",
        access_denied_message="deny",
        missing_username_message=RU_MESSAGES.access_denied_missing_username,
        invalid_request_message=RU_MESSAGES.invalid_request,
        missing_fields_message=RU_MESSAGES.missing_fields,
        no_route_matched_message=RU_MESSAGES.no_route_matched,
        locale="ru",
        routes=(default_route(200),),
    )

    decision = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text="Объект/здание: Башня А\nАвтомобиль: Ford Focus",
            user=UserProfile(id=10, username="alice"),
        )
    )

    assert decision.should_forward is False
    assert "дата и время прибытия" in decision.response_text
    assert "госномер" in decision.response_text


def test_service_routes_request_to_matching_destinations() -> None:
    """Multiple route rules should support one-to-many forwarding."""

    service = ResenderService(
        whitelist=Whitelist([10]),
        formatter=MessageFormatter(),
        request_accepted_message="ok",
        access_denied_message="deny",
        missing_username_message=RU_MESSAGES.access_denied_missing_username,
        invalid_request_message=RU_MESSAGES.invalid_request,
        missing_fields_message=RU_MESSAGES.missing_fields,
        no_route_matched_message=RU_MESSAGES.no_route_matched,
        locale="ru",
        routes=(
            RouteRule(
                name="tower",
                target_chat_id=200,
                allowed_usernames=frozenset({"alice"}),
                keywords_any=("башня",),
                keywords_none=(),
                template=None,
            ),
            RouteRule(
                name="all",
                target_chat_id=300,
                allowed_usernames=frozenset(),
                keywords_any=(),
                keywords_none=(),
                template="[{route}]\n{request}",
            ),
        ),
    )

    decision = service.handle_text(
        IncomingMessage(chat_id=1, text=VALID_REQUEST, user=UserProfile(id=10, username="alice"))
    )

    assert decision.should_forward is True
    assert decision.target_chat_ids == (200, 300)
    assert decision.forward_text is not None
    assert service.render_forward_text_for_target(300, decision.forward_text).startswith("[all]")


def test_service_matches_route_keywords_only_against_building_field() -> None:
    """Keywords in free-form fields must not add unintended destinations."""

    service = ResenderService(
        whitelist=Whitelist([10]),
        formatter=MessageFormatter(),
        request_accepted_message="ok",
        access_denied_message="deny",
        missing_username_message=RU_MESSAGES.access_denied_missing_username,
        invalid_request_message=RU_MESSAGES.invalid_request,
        missing_fields_message=RU_MESSAGES.missing_fields,
        no_route_matched_message=RU_MESSAGES.no_route_matched,
        locale="ru",
        routes=(
            RouteRule(
                name="tower-a",
                target_chat_id=200,
                allowed_usernames=frozenset(),
                keywords_any=("башня а",),
                keywords_none=(),
                template=None,
            ),
            RouteRule(
                name="tower-b",
                target_chat_id=300,
                allowed_usernames=frozenset(),
                keywords_any=("башня б",),
                keywords_none=(),
                template=None,
            ),
        ),
    )

    decision = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text=f"{VALID_REQUEST}\nКомментарий: пожалуйста не отправляйте в Башня Б",
            user=UserProfile(id=10, username="alice"),
        )
    )

    assert decision.should_forward is True
    assert decision.target_chat_ids == (200,)


def test_service_rejects_complete_request_when_no_route_matches() -> None:
    """A complete request should not be forwarded if all route filters reject it."""

    service = ResenderService(
        whitelist=Whitelist([10]),
        formatter=MessageFormatter(),
        request_accepted_message="ok",
        access_denied_message="deny",
        missing_username_message=RU_MESSAGES.access_denied_missing_username,
        invalid_request_message=RU_MESSAGES.invalid_request,
        missing_fields_message=RU_MESSAGES.missing_fields,
        no_route_matched_message=RU_MESSAGES.no_route_matched,
        locale="ru",
        routes=(
            RouteRule(
                name="garage",
                target_chat_id=200,
                allowed_usernames=frozenset(),
                keywords_any=("гараж",),
                keywords_none=(),
                template=None,
            ),
        ),
    )

    decision = service.handle_text(
        IncomingMessage(chat_id=1, text=VALID_REQUEST, user=UserProfile(id=10, username="alice"))
    )

    assert decision.should_forward is False
    assert decision.reason == "no_route_matched"
    assert decision.response_text == RU_MESSAGES.no_route_matched


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
