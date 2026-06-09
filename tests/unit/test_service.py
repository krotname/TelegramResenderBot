"""Unit tests for access-control and forwarding rules."""

from telegram_resender.formatting import MessageFormatter
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
    )

    approved = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text="Request",
            user=UserProfile(username="Alice"),
        )
    )
    denied_unknown = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text="Request",
            user=UserProfile(username="Charlie"),
        )
    )
    denied_missing = service.handle_text(
        IncomingMessage(
            chat_id=1,
            text="Request",
            user=UserProfile(username=None),
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
    assert denied_missing.response_text == "deny"
    assert denied_missing.reason == "missing_username"
