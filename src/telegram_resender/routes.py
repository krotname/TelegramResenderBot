"""Optional multi-route forwarding rules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telegram_resender.whitelist import normalize_username


@dataclass(frozen=True, slots=True)
class RouteRule:
    """A single forwarding route loaded from config."""

    name: str
    target_chat_id: int
    allowed_usernames: frozenset[str]
    keywords_any: tuple[str, ...]
    keywords_none: tuple[str, ...]
    template: str | None
    enabled: bool = True

    def matches(self, *, username: str | None, text: str) -> bool:
        """Return whether this route should receive the request."""

        if not self.enabled:
            return False
        normalized_username = normalize_username(username)
        if self.allowed_usernames and normalized_username not in self.allowed_usernames:
            return False
        normalized_text = text.casefold()
        if self.keywords_any and not any(
            keyword in normalized_text for keyword in self.keywords_any
        ):
            return False
        return not any(keyword in normalized_text for keyword in self.keywords_none)

    def render_forward_text(self, default_text: str) -> str:
        """Render route-specific text when a template is configured."""

        if self.template is None:
            return default_text
        return self.template.format(route=self.name, request=default_text)


def default_route(target_chat_id: int) -> RouteRule:
    """Build the backward-compatible single destination route."""

    return RouteRule(
        name="default",
        target_chat_id=target_chat_id,
        allowed_usernames=frozenset(),
        keywords_any=(),
        keywords_none=(),
        template=None,
    )


def load_routes(path: Path) -> tuple[RouteRule, ...]:
    """Load route rules from a JSON file."""

    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    raw_routes = payload.get("routes", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw_routes, list):
        msg = "Routes config must be a JSON list or an object with a 'routes' list"
        raise ValueError(msg)
    routes = tuple(_parse_route(item, index) for index, item in enumerate(raw_routes, start=1))
    if not routes:
        msg = "Routes config must contain at least one route"
        raise ValueError(msg)
    return routes


def _parse_route(item: Any, index: int) -> RouteRule:
    if not isinstance(item, dict):
        msg = f"Route #{index} must be an object"
        raise ValueError(msg)
    name = str(item.get("name") or f"route-{index}")
    if "target_chat_id" not in item:
        msg = f"Route '{name}' is missing target_chat_id"
        raise ValueError(msg)
    return RouteRule(
        name=name,
        target_chat_id=int(item["target_chat_id"]),
        allowed_usernames=_normalize_usernames(item.get("allowed_usernames", ())),
        keywords_any=_normalize_keywords(item.get("keywords_any", ())),
        keywords_none=_normalize_keywords(item.get("keywords_none", ())),
        template=_optional_string(item.get("template")),
        enabled=bool(item.get("enabled", True)),
    )


def _normalize_usernames(value: Any) -> frozenset[str]:
    return frozenset(
        username
        for item in _as_sequence(value)
        if (username := normalize_username(str(item))) is not None
    )


def _normalize_keywords(value: Any) -> tuple[str, ...]:
    return tuple(str(item).strip().casefold() for item in _as_sequence(value) if str(item).strip())


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _as_sequence(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)
