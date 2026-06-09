"""Formatting of forwarded Telegram requests."""

from __future__ import annotations

from telegram_resender.models import IncomingMessage, UserProfile


class MessageFormatter:
    """Build stable administrator-facing forwarding payloads."""

    def format_forward(self, message: IncomingMessage) -> str:
        """Format a message for the target group.

        The output is deliberately deterministic because admins may copy it into issue
        trackers, spreadsheets, or building access systems.
        """

        text = message.text.strip() or "<empty message>"
        lines = [
            "New Telegram request",
            f"From: {self._format_user(message.user)}",
            f"Source chat: {message.chat_id}",
            "",
            text,
        ]
        return "\n".join(lines)

    def _format_user(self, user: UserProfile) -> str:
        username = f"@{user.username}" if user.username else "unknown username"
        full_name = " ".join(part for part in (user.first_name, user.last_name) if part)
        return f"{full_name} ({username})" if full_name else username
