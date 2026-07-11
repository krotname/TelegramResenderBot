"""Optional multi-route forwarding rules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telegram_resender.telegram_limits import fits_telegram_message
from telegram_resender.whitelist import normalize_username, parse_user_id

_ROUTES_DOCUMENT_FIELDS = frozenset({"routes"})
_ROUTE_FIELDS = frozenset(
    {
        "name",
        "target_chat_id",
        "allowed_user_ids",
        "allowed_usernames",
        "keywords_any",
        "keywords_none",
        "template",
        "enabled",
    }
)


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
    allowed_user_ids: frozenset[int] = frozenset()

    def matches(self, *, username: str | None, text: str, user_id: int | None = None) -> bool:
        """Return whether this route should receive the request."""

        if not self.enabled:
            return False
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
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
        allowed_user_ids=frozenset(),
    )


def load_routes(path: Path) -> tuple[RouteRule, ...]:
    """Load route rules from a JSON file."""

    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream, object_pairs_hook=_reject_duplicate_keys)
    if isinstance(payload, dict):
        _reject_unknown_fields(
            payload,
            allowed_fields=_ROUTES_DOCUMENT_FIELDS,
            context="Routes config",
        )
        raw_routes = payload.get("routes")
    else:
        raw_routes = payload
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
    _reject_unknown_fields(item, allowed_fields=_ROUTE_FIELDS, context=f"Route #{index}")
    name = _parse_name(item.get("name"), index=index)
    if "target_chat_id" not in item:
        msg = f"Route '{name}' is missing target_chat_id"
        raise ValueError(msg)
    return RouteRule(
        name=name,
        target_chat_id=_parse_target_chat_id(item["target_chat_id"], route_name=name),
        allowed_user_ids=_normalize_user_ids(item.get("allowed_user_ids", ())),
        allowed_usernames=_normalize_usernames(item.get("allowed_usernames", ())),
        keywords_any=_normalize_keywords(item.get("keywords_any", ())),
        keywords_none=_normalize_keywords(item.get("keywords_none", ())),
        template=_parse_template(item.get("template"), route_name=name),
        enabled=_parse_enabled(item.get("enabled", True), route_name=name),
    )


def _parse_name(value: Any, *, index: int) -> str:
    if value is None:
        return f"route-{index}"
    if not isinstance(value, str) or not value.strip():
        msg = f"Route #{index} name must be a non-empty string"
        raise ValueError(msg)
    return value.strip()


def _parse_target_chat_id(value: Any, *, route_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        msg = f"Route '{route_name}' target_chat_id must be a non-zero integer"
        raise ValueError(msg)
    try:
        target_chat_id = int(value)
    except ValueError as exc:
        msg = f"Route '{route_name}' target_chat_id must be a non-zero integer"
        raise ValueError(msg) from exc
    if target_chat_id == 0:
        msg = f"Route '{route_name}' target_chat_id must be a non-zero integer"
        raise ValueError(msg)
    return target_chat_id


def _parse_enabled(value: Any, *, route_name: str) -> bool:
    if not isinstance(value, bool):
        msg = f"Route '{route_name}' enabled must be a boolean"
        raise ValueError(msg)
    return value


def _normalize_usernames(value: Any) -> frozenset[str]:
    normalized: set[str] = set()
    for item in _string_sequence(value, field_name="allowed_usernames"):
        username = normalize_username(item)
        if username is None:
            msg = "Route allowed_usernames must contain valid non-empty usernames"
            raise ValueError(msg)
        normalized.add(username)
    return frozenset(normalized)


def _normalize_user_ids(value: Any) -> frozenset[int]:
    parsed: set[int] = set()
    for item in _user_id_sequence(value):
        try:
            user_id = parse_user_id(item)
        except ValueError as exc:
            msg = "Route allowed_user_ids must contain positive integers"
            raise ValueError(msg) from exc
        if user_id is None:
            msg = "Route allowed_user_ids must contain positive integers"
            raise ValueError(msg)
        parsed.add(user_id)
    return frozenset(parsed)


def _normalize_keywords(value: Any) -> tuple[str, ...]:
    return tuple(
        item.strip().casefold()
        for item in _string_sequence(value, field_name="keyword filters")
        if item.strip()
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        msg = "Route template must be a string or null"
        raise ValueError(msg)
    if value == "":
        return None
    if not value.strip():
        msg = "Route template must contain non-whitespace text"
        raise ValueError(msg)
    return value


def _parse_template(value: Any, *, route_name: str) -> str | None:
    template = _optional_string(value)
    if template is None:
        return None
    try:
        rendered_sample = template.format(route=route_name, request="request")
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
        msg = f"Route '{route_name}' has invalid template: {exc}"
        raise ValueError(msg) from exc
    if not fits_telegram_message(rendered_sample):
        msg = f"Route '{route_name}' has invalid template: rendered text exceeds Telegram limits"
        raise ValueError(msg)
    return template


def _string_sequence(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        values = tuple(value)
    else:
        msg = f"Route {field_name} must be a string, a list of strings, or null"
        raise ValueError(msg)
    if any(not item.strip() for item in values):
        msg = f"Route {field_name} must contain only non-empty strings"
        raise ValueError(msg)
    return values


def _user_id_sequence(value: Any) -> tuple[int | str, ...]:
    if value is None:
        return ()
    if isinstance(value, bool):
        msg = "Route allowed_user_ids must be an integer, a list of integers, or null"
        raise ValueError(msg)
    if isinstance(value, (int, str)):
        values = (value,)
    elif isinstance(value, (list, tuple)) and all(
        isinstance(item, (int, str)) and not isinstance(item, bool) for item in value
    ):
        values = tuple(value)
    else:
        msg = "Route allowed_user_ids must be an integer, a list of integers, or null"
        raise ValueError(msg)
    return values


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            msg = f"Routes config contains duplicate JSON key {key!r}"
            raise ValueError(msg)
        result[key] = value
    return result


def _reject_unknown_fields(
    item: dict[Any, Any],
    *,
    allowed_fields: frozenset[str],
    context: str,
) -> None:
    unknown_fields = sorted(repr(key) for key in item if key not in allowed_fields)
    if not unknown_fields:
        return
    allowed = ", ".join(sorted(allowed_fields))
    unknown = ", ".join(unknown_fields)
    msg = f"{context} contains unknown field(s) {unknown}; allowed fields: {allowed}"
    raise ValueError(msg)
