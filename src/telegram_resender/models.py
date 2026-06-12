"""Small immutable models used by the forwarding domain layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Telegram user fields needed by the resender."""

    username: str | None
    first_name: str | None = None
    last_name: str | None = None


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    """Text message normalized away from the Telegram SDK."""

    chat_id: int
    text: str
    user: UserProfile
    message_id: int | None = None
    submitted_at: datetime | None = None


DecisionReason = Literal[
    "allowed_username",
    "missing_username",
    "unknown_username",
    "invalid_request",
    "no_route_matched",
]


@dataclass(frozen=True, slots=True)
class ForwardingDecision:
    """Result of applying access control to an incoming message."""

    should_forward: bool
    response_text: str
    reason: DecisionReason
    forward_text: str | None = None
    request_id: str | None = None
    target_chat_ids: tuple[int, ...] = ()
