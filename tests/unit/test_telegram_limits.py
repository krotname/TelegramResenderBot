"""Unit tests for Telegram UTF-16 message limits."""

from telegram_resender.telegram_limits import fits_telegram_message, telegram_utf16_length


def test_telegram_message_limit_uses_utf16_code_units() -> None:
    """Astral characters count as two units and exact boundary values remain valid."""

    assert telegram_utf16_length("😀") == 2
    assert fits_telegram_message("x" * 4096) is True
    assert fits_telegram_message("x" * 4097) is False
    assert fits_telegram_message("😀" * 2048) is True
    assert fits_telegram_message("😀" * 2049) is False


def test_telegram_message_limit_rejects_empty_or_invalid_unicode() -> None:
    """sendMessage requires non-empty valid Unicode text."""

    assert fits_telegram_message("") is False
    assert fits_telegram_message("\ud800") is False
