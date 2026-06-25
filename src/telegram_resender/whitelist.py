"""Whitelist loading and matching."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path


def parse_user_id(value: int | str | None) -> int | None:
    """Parse an immutable Telegram numeric user id from configuration or updates."""

    if value is None:
        return None
    if isinstance(value, int):
        return value
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError as exc:
        msg = f"Telegram user id must be an integer: {value!r}"
        raise ValueError(msg) from exc


def normalize_username(username: str | None) -> str | None:
    """Normalize Telegram usernames for display-only route matching."""

    if username is None:
        return None
    normalized = username.strip().removeprefix("@").lower()
    return normalized or None


class Whitelist:
    """Immutable set of allowed Telegram numeric user ids."""

    def __init__(self, user_ids: Iterable[int | str]) -> None:
        parsed = {user_id for item in user_ids if (user_id := parse_user_id(item)) is not None}
        self._user_ids = frozenset(parsed)

    @classmethod
    def from_file(cls, path: Path) -> Whitelist:
        """Load Telegram numeric user ids from the first column of a CSV file.

        The CSV reader is intentionally used even for one-value-per-line files: it keeps
        quoted values, UTF-8 BOMs, and future metadata columns predictable.
        """

        if not path.exists():
            msg = f"Whitelist file does not exist: {path}"
            raise FileNotFoundError(msg)

        user_ids: list[str] = []
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.reader(stream):
                if not row:
                    continue
                candidate = row[0].strip()
                if candidate and not candidate.startswith("#"):
                    user_ids.append(candidate)
        return cls(user_ids)

    def contains(self, user_id: int | str | None) -> bool:
        """Return whether a Telegram numeric user id may submit requests."""

        parsed = parse_user_id(user_id)
        return parsed in self._user_ids if parsed is not None else False

    @property
    def user_ids(self) -> frozenset[int]:
        """Allowed Telegram numeric user ids."""

        return self._user_ids

    @property
    def usernames(self) -> frozenset[str]:
        """Backward-compatible empty username set; usernames are not trusted."""

        return frozenset()

    @property
    def is_empty(self) -> bool:
        """Whether the whitelist contains no users."""

        return not self._user_ids
