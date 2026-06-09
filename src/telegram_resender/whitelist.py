"""Whitelist loading and matching."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path


def normalize_username(username: str | None) -> str | None:
    """Normalize Telegram usernames for case-insensitive whitelist matching."""

    if username is None:
        return None
    normalized = username.strip().removeprefix("@").lower()
    return normalized or None


class Whitelist:
    """Immutable set of allowed Telegram usernames."""

    def __init__(self, usernames: Iterable[str]) -> None:
        normalized = {username for item in usernames if (username := normalize_username(item))}
        self._usernames = frozenset(normalized)

    @classmethod
    def from_file(cls, path: Path) -> "Whitelist":
        """Load usernames from the first column of a CSV file.

        The CSV reader is intentionally used even for one-value-per-line files: it keeps
        quoted values, UTF-8 BOMs, and future metadata columns predictable.
        """

        if not path.exists():
            msg = f"Whitelist file does not exist: {path}"
            raise FileNotFoundError(msg)

        usernames: list[str] = []
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.reader(stream):
                if not row:
                    continue
                candidate = row[0].strip()
                if candidate and not candidate.startswith("#"):
                    usernames.append(candidate)
        return cls(usernames)

    def contains(self, username: str | None) -> bool:
        """Return whether a Telegram username is allowed to submit requests."""

        normalized = normalize_username(username)
        return normalized in self._usernames if normalized else False

    @property
    def usernames(self) -> frozenset[str]:
        """Allowed usernames normalized to lowercase and without leading ``@``."""

        return self._usernames

    @property
    def is_empty(self) -> bool:
        """Whether the whitelist contains no users."""

        return not self._usernames
