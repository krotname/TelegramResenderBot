"""SQLite request delivery log."""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal, TextIO

DeliveryStatus = Literal["pending", "delivered", "failed", "skipped"]


@dataclass(frozen=True, slots=True)
class DeliveryRecord:
    """A persisted delivery attempt row."""

    request_id: str
    target_chat_id: int
    sender_username: str | None
    created_at: str
    validation_status: str
    delivery_status: str
    last_error: str | None


class RequestLog:
    """Small SQLite-backed request delivery log."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def begin_delivery(
        self,
        *,
        request_id: str,
        target_chat_id: int,
        sender_username: str | None,
    ) -> bool:
        """Create or update a delivery row.

        Returns False when this request/target pair has already been delivered.
        """

        existing = self._get_status(request_id, target_chat_id)
        if existing == "delivered":
            return False
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO request_deliveries (
                  request_id, target_chat_id, sender_username, created_at,
                  validation_status, delivery_status, last_error
                )
                VALUES (?, ?, ?, ?, 'valid', 'pending', NULL)
                ON CONFLICT(request_id, target_chat_id) DO UPDATE SET
                  delivery_status = 'pending',
                  last_error = NULL
                """,
                (request_id, target_chat_id, sender_username, now),
            )
        return True

    def mark_delivery(
        self,
        *,
        request_id: str,
        target_chat_id: int,
        status: DeliveryStatus,
        error: str | None = None,
    ) -> None:
        """Persist delivery result for a request/target pair."""

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE request_deliveries
                SET delivery_status = ?, last_error = ?
                WHERE request_id = ? AND target_chat_id = ?
                """,
                (status, error, request_id, target_chat_id),
            )

    def records_since(self, since: date) -> tuple[DeliveryRecord, ...]:
        """Return delivery records created at or after the given date."""

        threshold = datetime.combine(since, datetime.min.time(), tzinfo=UTC).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT request_id, target_chat_id, sender_username, created_at,
                       validation_status, delivery_status, last_error
                FROM request_deliveries
                WHERE created_at >= ?
                ORDER BY created_at, request_id, target_chat_id
                """,
                (threshold,),
            ).fetchall()
        return tuple(DeliveryRecord(*row) for row in rows)

    def check(self) -> None:
        """Open the database and ensure the schema exists."""

        self._ensure_schema()

    def _get_status(self, request_id: str, target_chat_id: int) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT delivery_status
                FROM request_deliveries
                WHERE request_id = ? AND target_chat_id = ?
                """,
                (request_id, target_chat_id),
            ).fetchone()
        return str(row[0]) if row else None

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS request_deliveries (
                  request_id TEXT NOT NULL,
                  target_chat_id INTEGER NOT NULL,
                  sender_username TEXT,
                  created_at TEXT NOT NULL,
                  validation_status TEXT NOT NULL,
                  delivery_status TEXT NOT NULL,
                  last_error TEXT,
                  PRIMARY KEY (request_id, target_chat_id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)


def export_records_csv(records: Iterable[DeliveryRecord], stream: TextIO) -> None:
    """Write delivery records to CSV."""

    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        [
            "request_id",
            "target_chat_id",
            "sender_username",
            "created_at",
            "validation_status",
            "delivery_status",
            "last_error",
        ]
    )
    for record in records:
        writer.writerow(
            [
                record.request_id,
                record.target_chat_id,
                record.sender_username or "",
                record.created_at,
                record.validation_status,
                record.delivery_status,
                record.last_error or "",
            ]
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
