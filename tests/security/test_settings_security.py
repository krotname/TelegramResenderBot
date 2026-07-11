"""Security-oriented tests for startup configuration."""

import pytest

from telegram_resender.settings import Settings

VALID_BOT_TOKEN = f"123456789:{'A' * 35}"


def test_placeholder_token_is_rejected() -> None:
    """Refuse known placeholder values before startup."""

    with pytest.raises(ValueError, match="placeholder"):
        Settings(bot_token="changeme", forward_chat_id=1)


def test_bot_token_shape_is_validated() -> None:
    """Reject tokens that don't resemble Telegram credentials format."""

    with pytest.raises(ValueError, match="must look like a Telegram Bot API token"):
        Settings(bot_token="not-a-token", forward_chat_id=1)

    with pytest.raises(ValueError, match="must look like a Telegram Bot API token"):
        Settings(bot_token=":", forward_chat_id=1)

    for token in ("123::", "123:a:b", "123:short", f"123:{'ю' * 35}"):
        with pytest.raises(ValueError, match="must look like a Telegram Bot API token"):
            Settings(bot_token=token, forward_chat_id=1)

    assert Settings(bot_token=VALID_BOT_TOKEN, forward_chat_id=1).bot_token == VALID_BOT_TOKEN


def test_production_example_token_is_rejected_as_placeholder() -> None:
    """The copyable production example must not pass as a real credential."""

    with pytest.raises(ValueError, match="placeholder"):
        Settings(bot_token="123456:replace-me", forward_chat_id=1)


def test_zero_forward_chat_id_is_rejected() -> None:
    """Telegram chat ID zero can never be a valid delivery target."""

    with pytest.raises(ValueError):
        Settings(bot_token=VALID_BOT_TOKEN, forward_chat_id=0)


def test_admin_ids_are_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Admin IDs should be easy to configure from .env files."""

    monkeypatch.setenv("TELEGRAM_RESENDER_ADMIN_IDS", "100, 200")
    settings = Settings(bot_token=VALID_BOT_TOKEN, forward_chat_id=1)

    assert settings.admin_ids == frozenset({100, 200})


def test_malformed_admin_ids_are_rejected_during_settings_validation() -> None:
    """A bad admin ID must not remain latent until an admin command is handled."""

    with pytest.raises(ValueError, match="comma-separated integers"):
        Settings(
            bot_token=VALID_BOT_TOKEN,
            forward_chat_id=1,
            admin_ids_raw="100, not-an-id",
        )

    with pytest.raises(ValueError, match="greater than zero"):
        Settings(bot_token=VALID_BOT_TOKEN, forward_chat_id=1, admin_ids_raw="100, -1")


def test_pending_request_ttl_is_bounded() -> None:
    """Pending state must have a positive, operationally bounded lifetime."""

    with pytest.raises(ValueError):
        Settings(
            bot_token=VALID_BOT_TOKEN,
            forward_chat_id=1,
            pending_request_ttl_seconds=29,
        )
    with pytest.raises(ValueError):
        Settings(
            bot_token=VALID_BOT_TOKEN,
            forward_chat_id=1,
            pending_request_ttl_seconds=86_401,
        )


def test_delivery_lease_is_bounded() -> None:
    """Lease recovery must be neither immediate nor indefinitely stuck."""

    with pytest.raises(ValueError):
        Settings(bot_token=VALID_BOT_TOKEN, forward_chat_id=1, delivery_lease_seconds=29)
    with pytest.raises(ValueError):
        Settings(bot_token=VALID_BOT_TOKEN, forward_chat_id=1, delivery_lease_seconds=3_601)


def test_configurable_replies_use_telegram_utf16_limit() -> None:
    """Astral Unicode must count as two UTF-16 units for configurable replies."""

    accepted = "😀" * 2048
    settings = Settings(
        bot_token=VALID_BOT_TOKEN,
        forward_chat_id=1,
        request_accepted_message=accepted,
        access_denied_message=accepted,
    )
    assert settings.request_accepted_message == accepted
    assert settings.access_denied_message == accepted

    with pytest.raises(ValueError, match="4096 UTF-16"):
        Settings(
            bot_token=VALID_BOT_TOKEN,
            forward_chat_id=1,
            request_accepted_message="😀" * 2049,
        )
    with pytest.raises(ValueError, match="4096 UTF-16"):
        Settings(
            bot_token=VALID_BOT_TOKEN,
            forward_chat_id=1,
            access_denied_message="x" * 4097,
        )
