"""Unit tests for message rendering rules."""

from telegram_resender.formatting import MessageFormatter
from telegram_resender.models import IncomingMessage, UserProfile


def test_message_formatter_includes_source_and_author() -> None:
    """Ensure the formatted message is deterministic and human-readable."""

    formatter = MessageFormatter()
    rendered = formatter.format_forward(
        IncomingMessage(
            chat_id=1001,
            text="Tower A\nTime: 12:00\nCar: Ford",
            user=UserProfile(username="TestUser", first_name="Alex", last_name="M"),
        )
    )

    assert "New Telegram request" in rendered
    assert "From: Alex M (@TestUser)" in rendered
    assert "Source chat: 1001" in rendered
    assert "Tower A" in rendered
