"""Unit tests for message rendering rules."""

from datetime import UTC, datetime

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
            message_id=42,
            submitted_at=datetime(2026, 6, 12, 10, 30, tzinfo=UTC),
        )
    )

    assert "New Telegram request" in rendered
    assert "Request id: tg-1001-42" in rendered
    assert "Submitted at: 2026-06-12 10:30:00 UTC" in rendered
    assert "From: Alex M (@TestUser)" in rendered
    assert "Source chat: 1001" in rendered
    assert "Tower A" in rendered
