"""Unit tests for access-control and forwarding rules."""

from telegram_resender.formatting import MessageFormatter
from telegram_resender.messages import RU_MESSAGES
from telegram_resender.models import IncomingMessage, UserProfile
from telegram_resender.service import ResenderService
from telegram_resender.whitelist import Whitelist


def test_service_forwards_only_whitelisted() -> None:
    """A missing or unknown username should not be forwarded."""

    service = ResenderService(
        whitelist=Whitelist(["alice", "bob"]),
        formatter=MessageFormatter(),
        request_accepted_message="ok",
        access_denied_message="deny",
        missing_username_message=RU_MESSAGES.access_denied_missing_username,
        invalid_request_message=RU_MESSAGES.invalid_request,
    )

    approved = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text="Tower A, arrival 12:00, Ford, A123BC",
            user=UserProfile(username="Alice"),
        )
    )
    denied_unknown = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text="Tower A, arrival 12:00, Ford, A123BC",
            user=UserProfile(username="Charlie"),
        )
    )
    denied_missing = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text="Tower A, arrival 12:00, Ford, A123BC",
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

    assert denied_unknown.should_forward is False
    assert denied_unknown.response_text == "deny"
    assert denied_unknown.reason == "unknown_username"

    assert denied_missing.should_forward is False
    assert "chat id: 1" in denied_missing.response_text
    assert denied_missing.reason == "missing_username"

    assert invalid_request.should_forward is False
    assert invalid_request.response_text == RU_MESSAGES.invalid_request
    assert invalid_request.reason == "invalid_request"
