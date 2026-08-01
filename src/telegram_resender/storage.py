"""SQLite-backed delivery and pending-confirmation state."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from secrets import token_hex
from time import time
from typing import Any, Literal, TextIO

DeliveryStatus = Literal["pending", "delivered", "failed", "skipped"]
PendingRequestKey = tuple[int, int | None]
_DANGEROUS_CSV_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")
_MAX_STORED_ERROR_LENGTH = 2_000

_EXPECTED_DELIVERY_COLUMNS = (
    ("request_id", "TEXT", True),
    ("target_chat_id", "INTEGER", True),
    ("sender_username", "TEXT", False),
    ("created_at", "TEXT", True),
    ("validation_status", "TEXT", True),
    ("delivery_status", "TEXT", True),
    ("last_error", "TEXT", False),
)
_EXPECTED_DELIVERY_UNIQUE_INDEX = ("request_id", "target_chat_id")
_EXPECTED_DELIVERY_LEASE_COLUMNS = (
    ("request_id", "TEXT", True),
    ("target_chat_id", "INTEGER", True),
    ("owner_token", "TEXT", True),
    ("version", "INTEGER", True),
    ("lease_expires_at", "REAL", True),
)
_EXPECTED_PENDING_SEQUENCE_COLUMNS = (
    ("chat_id", "INTEGER", True),
    ("user_id", "INTEGER", True),
    ("current_version", "INTEGER", True),
)
_EXPECTED_PENDING_REQUEST_COLUMNS = (
    ("chat_id", "INTEGER", True),
    ("user_id", "INTEGER", True),
    ("version", "INTEGER", True),
    ("request_id", "TEXT", True),
    ("request_id_aliases", "TEXT", True),
    ("forward_payloads", "TEXT", True),
    ("sender_user_id", "INTEGER", True),
    ("sender_username", "TEXT", False),
    ("expires_at", "REAL", True),
    ("owner_token", "TEXT", False),
    ("owner_version", "INTEGER", True),
    ("owner_expires_at", "REAL", False),
)


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


@dataclass(frozen=True, slots=True)
class DeliveryLease:
    """Exclusive, versioned ownership of one request/target delivery."""

    request_id: str
    request_id_aliases: tuple[str, ...]
    target_chat_id: int
    owner_token: str
    version: int
    expires_at: float


class DeliveryInProgressError(RuntimeError):
    """Raised when another live owner already holds the delivery lease."""


@dataclass(frozen=True, slots=True)
class PendingRequest:
    """Persisted forwarding payload waiting for explicit confirmation."""

    version: int
    request_id: str
    request_id_aliases: tuple[str, ...]
    forward_text_by_chat_id: tuple[tuple[int, str], ...]
    sender_user_id: int
    sender_username: str | None
    route_match_text: str | None
    expires_at: float
    owner_token: str | None = None
    owner_version: int = 0
    owner_expires_at: float | None = None


class RequestLog:
    """SQLite delivery log with atomic, expiring ownership leases."""

    def __init__(self, path: Path, *, lease_seconds: int = 300) -> None:
        if lease_seconds <= 0:
            msg = "delivery lease duration must be positive"
            raise ValueError(msg)
        self._path = path
        self._lease_seconds = lease_seconds
        self._path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_storage_schema(self._path)

    def begin_delivery(
        self,
        *,
        request_id: str,
        target_chat_id: int,
        sender_username: str | None,
        request_id_aliases: tuple[str, ...] = (),
    ) -> DeliveryLease | None:
        """Atomically claim a request/target pair unless delivered or actively leased."""

        request_ids = _request_ids(request_id, request_id_aliases)
        now = time()
        owner_token = token_hex(16)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_statuses = _get_statuses(connection, request_ids, target_chat_id)
            if "delivered" in existing_statuses.values():
                return None

            placeholders = ", ".join("?" for _ in request_ids)
            claim_rows = connection.execute(
                f"""
                SELECT version, lease_expires_at
                FROM delivery_leases
                WHERE request_id IN ({placeholders}) AND target_chat_id = ?
                """,
                (*request_ids, target_chat_id),
            ).fetchall()
            if any(float(row[1]) > now for row in claim_rows):
                msg = f"request {request_id!r} is already being delivered to {target_chat_id}"
                raise DeliveryInProgressError(msg)

            version = max((int(row[0]) for row in claim_rows), default=0) + 1
            expires_at = now + self._lease_seconds
            for claimed_request_id in request_ids:
                connection.execute(
                    """
                    INSERT INTO delivery_leases (
                      request_id, target_chat_id, owner_token, version, lease_expires_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(request_id, target_chat_id) DO UPDATE SET
                      owner_token = excluded.owner_token,
                      version = excluded.version,
                      lease_expires_at = excluded.lease_expires_at
                    """,
                    (claimed_request_id, target_chat_id, owner_token, version, expires_at),
                )

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
                (request_id, target_chat_id, sender_username, _utc_now()),
            )
        return DeliveryLease(
            request_id=request_id,
            request_id_aliases=tuple(item for item in request_ids if item != request_id),
            target_chat_id=target_chat_id,
            owner_token=owner_token,
            version=version,
            expires_at=expires_at,
        )

    def mark_delivery(
        self,
        *,
        lease: DeliveryLease,
        status: DeliveryStatus,
        error: str | None = None,
    ) -> bool:
        """Persist a result only while the supplied owner/version still owns the lease."""

        request_ids = _request_ids(lease.request_id, lease.request_id_aliases)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not _owns_delivery_lease(
                connection,
                request_ids=request_ids,
                target_chat_id=lease.target_chat_id,
                owner_token=lease.owner_token,
                version=lease.version,
            ):
                return False

            connection.execute(
                """
                UPDATE request_deliveries
                SET delivery_status = ?, last_error = ?
                WHERE request_id = ? AND target_chat_id = ?
                """,
                (
                    status,
                    error[:_MAX_STORED_ERROR_LENGTH] if error is not None else None,
                    lease.request_id,
                    lease.target_chat_id,
                ),
            )
            placeholders = ", ".join("?" for _ in request_ids)
            connection.execute(
                f"""
                UPDATE delivery_leases
                SET lease_expires_at = 0
                WHERE request_id IN ({placeholders})
                  AND target_chat_id = ?
                  AND owner_token = ?
                  AND version = ?
                """,
                (*request_ids, lease.target_chat_id, lease.owner_token, lease.version),
            )
        return True

    def renew_delivery(self, lease: DeliveryLease, *, wait_seconds: float = 0.0) -> bool:
        """Extend a live lease across a known retry wait without changing ownership."""

        request_ids = _request_ids(lease.request_id, lease.request_id_aliases)
        new_expires_at = time() + self._lease_seconds + max(wait_seconds, 0.0)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not _owns_delivery_lease(
                connection,
                request_ids=request_ids,
                target_chat_id=lease.target_chat_id,
                owner_token=lease.owner_token,
                version=lease.version,
            ):
                return False
            placeholders = ", ".join("?" for _ in request_ids)
            connection.execute(
                f"""
                UPDATE delivery_leases
                SET lease_expires_at = ?
                WHERE request_id IN ({placeholders})
                  AND target_chat_id = ? AND owner_token = ? AND version = ?
                """,
                (
                    new_expires_at,
                    *request_ids,
                    lease.target_chat_id,
                    lease.owner_token,
                    lease.version,
                ),
            )
        return True

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
        """Open the database and validate every runtime storage table."""

        _ensure_storage_schema(self._path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with _connect(self._path) as connection:
            yield connection


class PendingRequestStore:
    """Persistent pending confirmations with TTL and versioned claim ownership."""

    def __init__(self, path: Path, *, ttl_seconds: int, claim_seconds: int = 300) -> None:
        if ttl_seconds <= 0 or claim_seconds <= 0:
            msg = "pending TTL and claim duration must be positive"
            raise ValueError(msg)
        self._path = path
        self._ttl_seconds = ttl_seconds
        self._claim_seconds = claim_seconds
        self._path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_storage_schema(self._path)

    def publish(
        self,
        key: PendingRequestKey,
        *,
        request_id: str,
        request_id_aliases: tuple[str, ...],
        forward_text_by_chat_id: tuple[tuple[int, str], ...],
        sender_user_id: int | None,
        sender_username: str | None,
        route_match_text: str | None = None,
    ) -> PendingRequest:
        """Publish a visible preview, replacing only an unclaimed duplicate ID."""

        chat_id, user_id = _require_pending_key(key)
        if sender_user_id != user_id:
            msg = "pending request owner must match its storage key"
            raise ValueError(msg)
        now = time()
        with _connect(self._path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            _purge_pending(connection, now)
            sequence_row = connection.execute(
                """
                SELECT current_version
                FROM pending_request_sequences
                WHERE chat_id = ? AND user_id = ?
                """,
                (chat_id, user_id),
            ).fetchone()
            version = (int(sequence_row[0]) if sequence_row else 0) + 1
            connection.execute(
                """
                INSERT INTO pending_request_sequences (chat_id, user_id, current_version)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                  current_version = excluded.current_version
                """,
                (chat_id, user_id, version),
            )
            connection.execute(
                """
                DELETE FROM pending_requests
                WHERE chat_id = ? AND user_id = ? AND request_id = ?
                  AND (owner_token IS NULL OR owner_expires_at <= ?)
                """,
                (chat_id, user_id, request_id, now),
            )
            expires_at = now + self._ttl_seconds
            connection.execute(
                """
                INSERT INTO pending_requests (
                  chat_id, user_id, version, request_id, request_id_aliases,
                  forward_payloads, sender_user_id, sender_username, expires_at,
                  owner_token, owner_version, owner_expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0, NULL)
                """,
                (
                    chat_id,
                    user_id,
                    version,
                    request_id,
                    json.dumps(request_id_aliases, ensure_ascii=False),
                    json.dumps(
                        {
                            "payloads": forward_text_by_chat_id,
                            "route_match_text": route_match_text,
                        },
                        ensure_ascii=False,
                    ),
                    sender_user_id,
                    sender_username,
                    expires_at,
                ),
            )
        return PendingRequest(
            version=version,
            request_id=request_id,
            request_id_aliases=request_id_aliases,
            forward_text_by_chat_id=forward_text_by_chat_id,
            sender_user_id=user_id,
            sender_username=sender_username,
            route_match_text=route_match_text,
            expires_at=expires_at,
        )

    def claim(
        self,
        key: PendingRequestKey,
        *,
        request_id: str | None = None,
    ) -> PendingRequest | None:
        """Atomically claim the latest matching visible request."""

        resolved_key = _optional_pending_key(key)
        if resolved_key is None:
            return None
        chat_id, user_id = resolved_key
        now = time()
        owner_token = token_hex(16)
        with _connect(self._path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            _prepare_pending_key(connection, chat_id=chat_id, user_id=user_id, now=now)
            parameters: list[object] = [chat_id, user_id, now]
            request_predicate = ""
            if request_id is not None:
                request_predicate = "AND request_id = ?"
                parameters.append(request_id)
            row = connection.execute(
                f"""
                SELECT version, request_id, request_id_aliases, forward_payloads,
                       sender_user_id, sender_username, expires_at,
                       owner_token, owner_version, owner_expires_at
                FROM pending_requests
                WHERE chat_id = ? AND user_id = ? AND expires_at > ?
                  AND owner_token IS NULL {request_predicate}
                ORDER BY version DESC
                LIMIT 1
                """,
                tuple(parameters),
            ).fetchone()
            if row is None:
                return None
            version = int(row[0])
            owner_version = int(row[8]) + 1
            owner_expires_at = now + self._claim_seconds
            updated = connection.execute(
                """
                UPDATE pending_requests
                SET owner_token = ?, owner_version = ?, owner_expires_at = ?
                WHERE chat_id = ? AND user_id = ? AND version = ? AND owner_token IS NULL
                """,
                (
                    owner_token,
                    owner_version,
                    owner_expires_at,
                    chat_id,
                    user_id,
                    version,
                ),
            )
            if updated.rowcount != 1:
                return None
            claimed_row = (*row[:7], owner_token, owner_version, owner_expires_at)
        return _pending_from_row(claimed_row)

    def release(self, key: PendingRequestKey, pending: PendingRequest) -> bool:
        """Release a failed claim for retry if its original preview TTL remains valid."""

        resolved_key = _optional_pending_key(key)
        if resolved_key is None or pending.owner_token is None:
            return False
        chat_id, user_id = resolved_key
        now = time()
        with _connect(self._path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if pending.expires_at <= now:
                connection.execute(
                    """
                    DELETE FROM pending_requests
                    WHERE chat_id = ? AND user_id = ? AND version = ?
                      AND owner_token = ? AND owner_version = ?
                    """,
                    (
                        chat_id,
                        user_id,
                        pending.version,
                        pending.owner_token,
                        pending.owner_version,
                    ),
                )
                return False
            updated = connection.execute(
                """
                UPDATE pending_requests
                SET owner_token = NULL, owner_expires_at = NULL
                WHERE chat_id = ? AND user_id = ? AND version = ?
                  AND owner_token = ? AND owner_version = ?
                """,
                (
                    chat_id,
                    user_id,
                    pending.version,
                    pending.owner_token,
                    pending.owner_version,
                ),
            )
            if updated.rowcount == 1:
                newest_row = connection.execute(
                    """
                    SELECT MAX(version)
                    FROM pending_requests
                    WHERE chat_id = ? AND user_id = ? AND request_id = ?
                      AND owner_token IS NULL AND expires_at > ?
                    """,
                    (chat_id, user_id, pending.request_id, now),
                ).fetchone()
                newest_version = int(newest_row[0]) if newest_row and newest_row[0] else None
                if newest_version is not None:
                    connection.execute(
                        """
                        DELETE FROM pending_requests
                        WHERE chat_id = ? AND user_id = ? AND request_id = ?
                          AND owner_token IS NULL AND version <> ?
                        """,
                        (chat_id, user_id, pending.request_id, newest_version),
                    )
        return updated.rowcount == 1

    def complete(self, key: PendingRequestKey, pending: PendingRequest) -> bool:
        """Delete a successfully handled request only for its current owner/version."""

        resolved_key = _optional_pending_key(key)
        if resolved_key is None or pending.owner_token is None:
            return False
        chat_id, user_id = resolved_key
        with _connect(self._path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            deleted = connection.execute(
                """
                DELETE FROM pending_requests
                WHERE chat_id = ? AND user_id = ? AND version = ?
                  AND owner_token = ? AND owner_version = ?
                """,
                (
                    chat_id,
                    user_id,
                    pending.version,
                    pending.owner_token,
                    pending.owner_version,
                ),
            )
        return deleted.rowcount == 1

    def renew(
        self,
        key: PendingRequestKey,
        pending: PendingRequest,
        *,
        wait_seconds: float = 0.0,
    ) -> bool:
        """Extend a live confirmation claim across a known delivery retry wait."""

        resolved_key = _optional_pending_key(key)
        if resolved_key is None or pending.owner_token is None:
            return False
        chat_id, user_id = resolved_key
        owner_expires_at = time() + self._claim_seconds + max(wait_seconds, 0.0)
        with _connect(self._path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                """
                UPDATE pending_requests
                SET owner_expires_at = ?
                WHERE chat_id = ? AND user_id = ? AND version = ?
                  AND owner_token = ? AND owner_version = ?
                """,
                (
                    owner_expires_at,
                    chat_id,
                    user_id,
                    pending.version,
                    pending.owner_token,
                    pending.owner_version,
                ),
            )
        return updated.rowcount == 1

    def cancel(
        self,
        key: PendingRequestKey,
        *,
        request_id: str | None = None,
    ) -> PendingRequest | None:
        """Atomically remove the latest matching request unless it is actively claimed."""

        resolved_key = _optional_pending_key(key)
        if resolved_key is None:
            return None
        chat_id, user_id = resolved_key
        now = time()
        with _connect(self._path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            _prepare_pending_key(connection, chat_id=chat_id, user_id=user_id, now=now)
            parameters: list[object] = [chat_id, user_id, now]
            request_predicate = ""
            if request_id is not None:
                request_predicate = "AND request_id = ?"
                parameters.append(request_id)
            row = connection.execute(
                f"""
                SELECT version, request_id, request_id_aliases, forward_payloads,
                       sender_user_id, sender_username, expires_at,
                       owner_token, owner_version, owner_expires_at
                FROM pending_requests
                WHERE chat_id = ? AND user_id = ? AND expires_at > ?
                  AND owner_token IS NULL {request_predicate}
                ORDER BY version DESC
                LIMIT 1
                """,
                tuple(parameters),
            ).fetchone()
            if row is None:
                return None
            pending = _pending_from_row(row)
            deleted = connection.execute(
                """
                DELETE FROM pending_requests
                WHERE chat_id = ? AND user_id = ? AND version = ? AND owner_token IS NULL
                """,
                (chat_id, user_id, pending.version),
            )
            if deleted.rowcount != 1:
                return None
        return pending

    def discard_all(self, key: PendingRequestKey) -> None:
        """Remove every pending request for a user/chat pair."""

        resolved_key = _optional_pending_key(key)
        if resolved_key is None:
            return
        with _connect(self._path) as connection:
            connection.execute(
                "DELETE FROM pending_requests WHERE chat_id = ? AND user_id = ?",
                resolved_key,
            )


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
                _safe_csv_cell(record.request_id),
                record.target_chat_id,
                _safe_csv_cell(record.sender_username),
                _safe_csv_cell(record.created_at),
                _safe_csv_cell(record.validation_status),
                _safe_csv_cell(record.delivery_status),
                _safe_csv_cell(record.last_error),
            ]
        )


def _request_ids(request_id: str, request_id_aliases: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((request_id, *request_id_aliases)))


def _get_statuses(
    connection: sqlite3.Connection,
    request_ids: tuple[str, ...],
    target_chat_id: int,
) -> dict[str, str]:
    placeholders = ", ".join("?" for _ in request_ids)
    rows = connection.execute(
        f"""
        SELECT request_id, delivery_status
        FROM request_deliveries
        WHERE request_id IN ({placeholders}) AND target_chat_id = ?
        """,
        (*request_ids, target_chat_id),
    ).fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def _owns_delivery_lease(
    connection: sqlite3.Connection,
    *,
    request_ids: tuple[str, ...],
    target_chat_id: int,
    owner_token: str,
    version: int,
) -> bool:
    """Require one owner/version across the primary request ID and every alias."""

    placeholders = ", ".join("?" for _ in request_ids)
    rows = connection.execute(
        f"""
        SELECT request_id, owner_token, version
        FROM delivery_leases
        WHERE request_id IN ({placeholders}) AND target_chat_id = ?
        """,
        (*request_ids, target_chat_id),
    ).fetchall()
    expected_owner = (owner_token, version)
    return len(rows) == len(request_ids) and all(
        (str(row[1]), int(row[2])) == expected_owner for row in rows
    )


def _pending_from_row(row: tuple[Any, ...]) -> PendingRequest:
    try:
        aliases_value = json.loads(str(row[2]))
        stored_payloads = json.loads(str(row[3]))
        if isinstance(stored_payloads, dict):
            payloads_value = stored_payloads.get("payloads")
            route_match_text = stored_payloads.get("route_match_text")
            if route_match_text is not None and not isinstance(route_match_text, str):
                raise ValueError
        else:
            # Legacy rows lack the context needed for safe route revalidation.
            payloads_value = stored_payloads
            route_match_text = None
        if not isinstance(aliases_value, list) or not all(
            isinstance(item, str) for item in aliases_value
        ):
            raise ValueError
        if not isinstance(payloads_value, list) or not all(
            isinstance(item, list)
            and len(item) == 2
            and isinstance(item[0], int)
            and not isinstance(item[0], bool)
            and isinstance(item[1], str)
            for item in payloads_value
        ):
            raise ValueError
        return PendingRequest(
            version=int(row[0]),
            request_id=str(row[1]),
            request_id_aliases=tuple(aliases_value),
            forward_text_by_chat_id=tuple((int(item[0]), str(item[1])) for item in payloads_value),
            sender_user_id=int(row[4]),
            sender_username=str(row[5]) if row[5] is not None else None,
            route_match_text=route_match_text,
            expires_at=float(row[6]),
            owner_token=str(row[7]) if row[7] is not None else None,
            owner_version=int(row[8]),
            owner_expires_at=float(row[9]) if row[9] is not None else None,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        msg = "pending_requests contains invalid serialized data"
        raise sqlite3.DatabaseError(msg) from exc


def _require_pending_key(key: PendingRequestKey) -> tuple[int, int]:
    resolved = _optional_pending_key(key)
    if resolved is None:
        msg = "pending requests require a Telegram user ID"
        raise ValueError(msg)
    return resolved


def _optional_pending_key(key: PendingRequestKey) -> tuple[int, int] | None:
    chat_id, user_id = key
    return (chat_id, user_id) if user_id is not None else None


def _purge_pending(connection: sqlite3.Connection, now: float) -> None:
    connection.execute(
        """
        UPDATE pending_requests
        SET owner_token = NULL, owner_expires_at = NULL
        WHERE owner_token IS NOT NULL AND owner_expires_at <= ?
        """,
        (now,),
    )
    connection.execute(
        "DELETE FROM pending_requests WHERE expires_at <= ? AND owner_token IS NULL",
        (now,),
    )


def _prepare_pending_key(
    connection: sqlite3.Connection,
    *,
    chat_id: int,
    user_id: int,
    now: float,
) -> None:
    connection.execute(
        """
        UPDATE pending_requests
        SET owner_token = NULL, owner_expires_at = NULL
        WHERE chat_id = ? AND user_id = ?
          AND owner_token IS NOT NULL AND owner_expires_at <= ?
        """,
        (chat_id, user_id, now),
    )
    connection.execute(
        """
        DELETE FROM pending_requests
        WHERE chat_id = ? AND user_id = ? AND expires_at <= ? AND owner_token IS NULL
        """,
        (chat_id, user_id, now),
    )


def _safe_csv_cell(value: str | None) -> str:
    if not value:
        return ""
    if value.startswith(_DANGEROUS_CSV_PREFIXES):
        return f"'{value}"
    return value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _ensure_storage_schema(path: Path) -> None:
    with _connect(path) as connection:
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS delivery_leases (
              request_id TEXT NOT NULL,
              target_chat_id INTEGER NOT NULL,
              owner_token TEXT NOT NULL,
              version INTEGER NOT NULL,
              lease_expires_at REAL NOT NULL,
              PRIMARY KEY (request_id, target_chat_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_request_sequences (
              chat_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              current_version INTEGER NOT NULL,
              PRIMARY KEY (chat_id, user_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_requests (
              chat_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              version INTEGER NOT NULL,
              request_id TEXT NOT NULL,
              request_id_aliases TEXT NOT NULL,
              forward_payloads TEXT NOT NULL,
              sender_user_id INTEGER NOT NULL,
              sender_username TEXT,
              expires_at REAL NOT NULL,
              owner_token TEXT,
              owner_version INTEGER NOT NULL,
              owner_expires_at REAL,
              PRIMARY KEY (chat_id, user_id, version)
            )
            """
        )
        _validate_table_schema(
            connection,
            table="request_deliveries",
            expected_columns=_EXPECTED_DELIVERY_COLUMNS,
            expected_primary_key=_EXPECTED_DELIVERY_UNIQUE_INDEX,
        )
        _validate_table_schema(
            connection,
            table="delivery_leases",
            expected_columns=_EXPECTED_DELIVERY_LEASE_COLUMNS,
            expected_primary_key=("request_id", "target_chat_id"),
        )
        _validate_table_schema(
            connection,
            table="pending_request_sequences",
            expected_columns=_EXPECTED_PENDING_SEQUENCE_COLUMNS,
            expected_primary_key=("chat_id", "user_id"),
        )
        _validate_table_schema(
            connection,
            table="pending_requests",
            expected_columns=_EXPECTED_PENDING_REQUEST_COLUMNS,
            expected_primary_key=("chat_id", "user_id", "version"),
        )


def _validate_delivery_schema(connection: sqlite3.Connection) -> None:
    """Backward-compatible helper retained for focused schema tests."""

    _validate_table_schema(
        connection,
        table="request_deliveries",
        expected_columns=_EXPECTED_DELIVERY_COLUMNS,
        expected_primary_key=_EXPECTED_DELIVERY_UNIQUE_INDEX,
    )


def _validate_table_schema(
    connection: sqlite3.Connection,
    *,
    table: str,
    expected_columns: tuple[tuple[str, str, bool], ...],
    expected_primary_key: tuple[str, ...],
) -> None:
    column_rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    actual_columns = tuple((str(row[1]), str(row[2]).upper(), bool(row[3])) for row in column_rows)
    if actual_columns != expected_columns:
        msg = (
            f"{table} schema mismatch: expected columns "
            f"{expected_columns!r}, got {actual_columns!r}"
        )
        raise sqlite3.DatabaseError(msg)

    index_rows = connection.execute(f"PRAGMA index_list({table})").fetchall()
    for index_row in index_rows:
        index_name = str(index_row[1])
        is_unique = bool(index_row[2])
        is_primary_key = len(index_row) > 3 and str(index_row[3]) == "pk"
        is_partial = bool(index_row[4]) if len(index_row) > 4 else False
        if not is_unique or not is_primary_key or is_partial:
            continue
        indexed_columns = tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM pragma_index_info(?) ORDER BY seqno",
                (index_name,),
            ).fetchall()
        )
        if indexed_columns == expected_primary_key:
            return

    key = ", ".join(expected_primary_key)
    msg = f"{table} schema mismatch: missing primary key on ({key})"
    raise sqlite3.DatabaseError(msg)
