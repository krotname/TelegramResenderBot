"""Security-oriented tests for startup configuration."""

import pytest

from telegram_resender.settings import Settings


def test_placeholder_token_is_rejected() -> None:
    """Refuse known placeholder values before startup."""

    with pytest.raises(ValueError, match="placeholder"):
        Settings(bot_token="changeme", forward_chat_id=1)


def test_bot_token_shape_is_validated() -> None:
    """Reject tokens that don't resemble Telegram credentials format."""

    with pytest.raises(ValueError, match="must look like a Telegram Bot API token"):
        Settings(bot_token="not-a-token", forward_chat_id=1)


def test_admin_ids_are_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Admin IDs should be easy to configure from .env files."""

    monkeypatch.setenv("TELEGRAM_RESENDER_ADMIN_IDS", "100, 200")
    settings = Settings(bot_token="123:abc", forward_chat_id=1)

    assert settings.admin_ids == frozenset({100, 200})
