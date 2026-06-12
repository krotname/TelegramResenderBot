"""Formatting of forwarded Telegram requests."""

from __future__ import annotations

import hashlib
from datetime import UTC

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
            f"Request id: {self._format_request_id(message)}",
            f"Submitted at: {self._format_submitted_at(message)}",
            f"From: {self._format_user(message.user)}",
            f"Source chat: {message.chat_id}",
            "",
            text,
        ]
        return "\n".join(lines)

    def _format_request_id(self, message: IncomingMessage) -> str:
        if message.message_id is not None:
            return f"tg-{message.chat_id}-{message.message_id}"
        fingerprint = hashlib.sha256(
            f"{message.chat_id}|{message.user.username or ''}|{message.text}".encode()
        ).hexdigest()
        return f"local-{fingerprint[:12]}"

    def _format_submitted_at(self, message: IncomingMessage) -> str:
        if message.submitted_at is None:
            return "unknown"
        submitted_at = message.submitted_at
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=UTC)
        return submitted_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _format_user(self, user: UserProfile) -> str:
        username = f"@{user.username}" if user.username else "unknown username"
        full_name = " ".join(part for part in (user.first_name, user.last_name) if part)
        return f"{full_name} ({username})" if full_name else username
