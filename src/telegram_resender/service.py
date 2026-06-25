"""Business rules for accepting and forwarding requests."""

from __future__ import annotations

from pathlib import Path

from telegram_resender.formatting import MessageFormatter
from telegram_resender.models import ForwardingDecision, IncomingMessage
from telegram_resender.requests import format_missing_fields, parse_request
from telegram_resender.routes import RouteRule
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
        missing_fields_message: str,
        no_route_matched_message: str,
        locale: str,
        routes: tuple[RouteRule, ...],
    ) -> None:
        self._whitelist = whitelist
        self._formatter = formatter
        self._request_accepted_message = request_accepted_message
        self._access_denied_message = access_denied_message
        self._missing_username_message = missing_username_message
        self._invalid_request_message = invalid_request_message
        self._missing_fields_message = missing_fields_message
        self._no_route_matched_message = no_route_matched_message
        self._locale = locale
        self._routes = routes

    @property
    def whitelist_count(self) -> int:
        """Number of Telegram user ids currently allowed by the service."""

        return len(self._whitelist.user_ids)

    def reload_whitelist(self, path: Path) -> int:
        """Reload whitelist from disk and return the new user count."""

        self._whitelist = Whitelist.from_file(path)
        return self.whitelist_count

    def handle_text(self, message: IncomingMessage) -> ForwardingDecision:
        """Decide whether a text message should be forwarded.

        A missing Telegram numeric user id is denied explicitly. Usernames are public,
        mutable handles, so they must not be used as the trust boundary.
        """

        if message.user.id is None:
            return ForwardingDecision(
                should_forward=False,
                response_text=self._missing_username_message.format(chat_id=message.chat_id),
                reason="missing_user_id",
            )

        if not self._whitelist.contains(message.user.id):
            return ForwardingDecision(
                should_forward=False,
                response_text=self._access_denied_message,
                reason="unknown_user_id",
            )

        if not message.text.strip() or not self._looks_like_request(message.text):
            return ForwardingDecision(
                should_forward=False,
                response_text=self._invalid_request_message,
                reason="invalid_request",
            )

        parsed_request = parse_request(message.text)
        if not parsed_request.is_complete:
            missing_fields = format_missing_fields(
                parsed_request.missing_fields,
                locale=self._locale,
            )
            return ForwardingDecision(
                should_forward=False,
                response_text=self._missing_fields_message.format(fields=missing_fields),
                reason="invalid_request",
            )

        request_id = self._formatter.format_request_id(message)
        matching_routes = tuple(
            route
            for route in self._routes
            if route.matches(username=message.user.username, text=message.text)
        )
        if not matching_routes:
            return ForwardingDecision(
                should_forward=False,
                response_text=self._no_route_matched_message,
                reason="no_route_matched",
                request_id=request_id,
            )
        forward_text = self._formatter.format_forward(message)
        return ForwardingDecision(
            should_forward=True,
            response_text=self._request_accepted_message,
            reason="allowed_user_id",
            forward_text=forward_text,
            request_id=request_id,
            target_chat_ids=tuple(route.target_chat_id for route in matching_routes),
        )

    def render_forward_text_for_target(self, target_chat_id: int, default_text: str) -> str:
        """Apply route template for the matched target if configured."""

        for route in self._routes:
            if route.target_chat_id == target_chat_id:
                return route.render_forward_text(default_text)
        return default_text

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
