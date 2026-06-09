"""Conversation-oriented tests for visible bot behavior."""

from telegram_resender.formatting import MessageFormatter
from telegram_resender.messages import (
    CAR_MODE_MESSAGE,
    HELP_MESSAGE,
    REQUEST_ACCEPTED_MESSAGE,
    START_MESSAGE,
)
from telegram_resender.models import IncomingMessage, UserProfile
from telegram_resender.service import ResenderService
from telegram_resender.whitelist import Whitelist


def test_conversation_commands_and_request_flow() -> None:
    """Mirror an operator conversation without Telegram SDK dependency."""

    service = ResenderService(
        whitelist=Whitelist(["alice"]),
        formatter=MessageFormatter(),
        request_accepted_message=REQUEST_ACCEPTED_MESSAGE,
        access_denied_message="deny",
    )

    bot_flow = []
    admin_flow = []

    def _run(message: IncomingMessage) -> str:
        decision = service.handle_text(message)
        if decision.should_forward and decision.forward_text is not None:
            admin_flow.append(decision.forward_text)
        return decision.response_text

    assert START_MESSAGE
    assert HELP_MESSAGE
    assert CAR_MODE_MESSAGE

    bot_flow.append(
        _run(
            IncomingMessage(
                chat_id=100,
                text="Hello",
                user=UserProfile(username="alice"),
            )
        )
    )
    bot_flow.append(
        _run(
            IncomingMessage(
                chat_id=100,
                text="Hello",
                user=UserProfile(username="stranger"),
            )
        )
    )
    bot_flow.append(
        _run(
            IncomingMessage(
                chat_id=100,
                text="",
                user=UserProfile(username=None),
            )
        )
    )

    assert bot_flow == [REQUEST_ACCEPTED_MESSAGE, "deny", "deny"]
    assert len(admin_flow) == 1
    assert "Source chat: 100" in admin_flow[0]
    assert "New Telegram request" in admin_flow[0]
