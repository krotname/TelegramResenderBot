"""Business rules for accepting and forwarding requests."""

from __future__ import annotations

from telegram_resender.formatting import MessageFormatter
from telegram_resender.models import ForwardingDecision, IncomingMessage
from telegram_resender.whitelist import Whitelist


class ResenderService:
    """Apply access control and produce forwarding decisions."""

    def __init__(
        self,
        whitelist: Whitelist,
        formatter: MessageFormatter,
        request_accepted_message: str,
        access_denied_message: str,
        missing_username_message: str,
        invalid_request_message: str,
    ) -> None:
        self._whitelist = whitelist
        self._formatter = formatter
        self._request_accepted_message = request_accepted_message
        self._access_denied_message = access_denied_message
        self._missing_username_message = missing_username_message
        self._invalid_request_message = invalid_request_message

    def handle_text(self, message: IncomingMessage) -> ForwardingDecision:
        """Decide whether a text message should be forwarded.

        A missing Telegram username is denied even if the chat id is known. The original
        bot used usernames as the trust boundary, so this keeps the rule explicit and
        testable instead of silently broadening access.
        """

        if message.user.username is None:
            return ForwardingDecision(
                should_forward=False,
                response_text=self._missing_username_message.format(chat_id=message.chat_id),
                reason="missing_username",
            )

        if not self._whitelist.contains(message.user.username):
            return ForwardingDecision(
                should_forward=False,
                response_text=self._access_denied_message,
                reason="unknown_username",
            )

        if not self._looks_like_request(message.text):
            return ForwardingDecision(
                should_forward=False,
                response_text=self._invalid_request_message,
                reason="invalid_request",
            )

        return ForwardingDecision(
            should_forward=True,
            response_text=self._request_accepted_message,
            reason="allowed_username",
            forward_text=self._formatter.format_forward(message),
        )

    def _looks_like_request(self, text: str) -> bool:
        """Reject empty greetings that are clearly not actionable requests."""

        normalized = " ".join(text.strip().lower().split())
        if len(normalized) < 10:
            return False
        return normalized not in {
            "hello",
            "hi",
            "hey",
            "привет",
            "здравствуйте",
            "добрый день",
        }
