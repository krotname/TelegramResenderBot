"""Telegram text length helpers shared by configuration and handlers."""

from __future__ import annotations

TELEGRAM_MESSAGE_MAX_UTF16_UNITS = 4096


def telegram_utf16_length(text: str) -> int:
    """Return the length Telegram uses for text/entity offsets."""

    return len(text.encode("utf-16-le")) // 2


def fits_telegram_message(text: str) -> bool:
    """Return whether text fits Telegram's sendMessage UTF-16 limit."""

    try:
        length = telegram_utf16_length(text)
    except UnicodeEncodeError:
        return False
    return 1 <= length <= TELEGRAM_MESSAGE_MAX_UTF16_UNITS
