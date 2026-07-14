"""Unit tests for SQLite request delivery storage."""

import sqlite3
from datetime import date
from io import StringIO
from pathlib import Path

import pytest

import telegram_resender.storage as storage_module
from telegram_resender.storage import (
    DeliveryInProgressError,
    PendingRequestStore,
    RequestLog,
    export_records_csv,
)


def test_request_log_tracks_delivery_idempotently(tmp_path: Path) -> None:
    """Delivered request/target pairs should not be sent again."""

    request_log = RequestLog(tmp_path / "requests.sqlite3")

    lease = request_log.begin_delivery(
        request_id="req-1",
        target_chat_id=100,
        sender_username="alice",
    )
    assert lease is not None
    request_log.mark_delivery(lease=lease, status="delivered")

    assert not request_log.begin_delivery(
        request_id="req-1",
        target_chat_id=100,
        sender_username="alice",
    )


def test_request_log_honors_legacy_request_id_alias(tmp_path: Path) -> None:
    """A delivered pre-upgrade local ID must suppress its new immutable-ID replacement."""

    request_log = RequestLog(tmp_path / "requests.sqlite3")
    lease = request_log.begin_delivery(
        request_id="local-legacy",
        target_chat_id=100,
        sender_username="alice",
    )
    assert lease is not None
    request_log.mark_delivery(lease=lease, status="delivered")

    assert not request_log.begin_delivery(
        request_id="local-current",
        request_id_aliases=("local-legacy",),
        target_chat_id=100,
        sender_username="alice",
    )


def test_delivery_lease_blocks_concurrency_and_rejects_stale_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only one owner may deliver, and an expired owner cannot finish a newer lease."""

    now = [100.0]
    monkeypatch.setattr(storage_module, "time", lambda: now[0])
    request_log = RequestLog(tmp_path / "requests.sqlite3", lease_seconds=30)

    first = request_log.begin_delivery(
        request_id="req-1",
        target_chat_id=100,
        sender_username="alice",
    )
    assert first is not None
    with pytest.raises(DeliveryInProgressError):
        request_log.begin_delivery(
            request_id="req-1",
            target_chat_id=100,
            sender_username="alice",
        )

    now[0] += 20
    assert request_log.renew_delivery(first, wait_seconds=20) is True
    now[0] += 15
    with pytest.raises(DeliveryInProgressError):
        request_log.begin_delivery(
            request_id="req-1",
            target_chat_id=100,
            sender_username="alice",
        )

    now[0] += 36
    second = request_log.begin_delivery(
        request_id="req-1",
        target_chat_id=100,
        sender_username="alice",
    )
    assert second is not None
    assert second.version == first.version + 1
    assert second.owner_token != first.owner_token
    assert request_log.mark_delivery(lease=first, status="delivered") is False
    assert request_log.mark_delivery(lease=second, status="delivered") is True
    assert (
        request_log.begin_delivery(
            request_id="req-1",
            target_chat_id=100,
            sender_username="alice",
        )
        is None
    )


def test_delivery_lease_alias_rejects_partially_superseded_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reclaiming a legacy alias must fence the old owner of the full alias set."""

    now = [100.0]
    monkeypatch.setattr(storage_module, "time", lambda: now[0])
    request_log = RequestLog(tmp_path / "requests.sqlite3", lease_seconds=30)
    first = request_log.begin_delivery(
        request_id="local-current",
        request_id_aliases=("local-legacy",),
        target_chat_id=100,
        sender_username="alice",
    )
    assert first is not None

    now[0] += 31
    second = request_log.begin_delivery(
        request_id="local-legacy",
        target_chat_id=100,
        sender_username="alice",
    )
    assert second is not None

    assert request_log.renew_delivery(first) is False
    assert request_log.mark_delivery(lease=first, status="delivered") is False
    assert request_log.mark_delivery(lease=second, status="delivered") is True
    assert (
        request_log.begin_delivery(
            request_id="local-current",
            request_id_aliases=("local-legacy",),
            target_chat_id=100,
            sender_username="alice",
        )
        is None
    )


def test_pending_store_persists_and_versions_stale_claims(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pending ownership must survive restart and reject a superseded worker."""

    now = [100.0]
    monkeypatch.setattr(storage_module, "time", lambda: now[0])
    path = tmp_path / "requests.sqlite3"
    first_store = PendingRequestStore(path, ttl_seconds=120, claim_seconds=30)
    published = first_store.publish(
        (100, 10),
        request_id="req-1",
        request_id_aliases=("legacy-1",),
        forward_text_by_chat_id=((200, "payload"),),
        sender_user_id=10,
        sender_username="alice",
    )

    restarted_store = PendingRequestStore(path, ttl_seconds=120, claim_seconds=30)
    first_claim = restarted_store.claim((100, 10), request_id="req-1")
    assert first_claim is not None
    assert first_claim.version == published.version
    assert first_store.claim((100, 10), request_id="req-1") is None

    now[0] += 31
    second_claim = first_store.claim((100, 10), request_id="req-1")
    assert second_claim is not None
    assert second_claim.version == first_claim.version
    assert second_claim.owner_version == first_claim.owner_version + 1
    assert second_claim.owner_token != first_claim.owner_token
    assert restarted_store.release((100, 10), first_claim) is False
    assert restarted_store.complete((100, 10), first_claim) is False
    assert first_store.release((100, 10), second_claim) is True

    third_claim = restarted_store.claim((100, 10), request_id="req-1")
    assert third_claim is not None
    assert third_claim.owner_version == second_claim.owner_version + 1
    assert restarted_store.complete((100, 10), third_claim) is True
    assert first_store.claim((100, 10), request_id="req-1") is None


def test_pending_publish_replaces_only_unclaimed_duplicate(
    tmp_path: Path,
) -> None:
    """Replayed previews with one ID must not leave hidden duplicate confirmations."""

    store = PendingRequestStore(tmp_path / "requests.sqlite3", ttl_seconds=120)
    first = store.publish(
        (100, 10),
        request_id="req-1",
        request_id_aliases=(),
        forward_text_by_chat_id=((200, "old"),),
        sender_user_id=10,
        sender_username="alice",
    )
    second = store.publish(
        (100, 10),
        request_id="req-1",
        request_id_aliases=(),
        forward_text_by_chat_id=((200, "new"),),
        sender_user_id=10,
        sender_username="alice",
    )
    assert second.version > first.version

    cancelled = store.cancel((100, 10), request_id="req-1")
    assert cancelled is not None
    assert cancelled.forward_text_by_chat_id == ((200, "new"),)
    assert store.cancel((100, 10), request_id="req-1") is None


def test_pending_claim_renewal_covers_retry_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A known retry delay must not let another confirmation supersede its owner."""

    now = [100.0]
    monkeypatch.setattr(storage_module, "time", lambda: now[0])
    store = PendingRequestStore(tmp_path / "requests.sqlite3", ttl_seconds=120, claim_seconds=30)
    store.publish(
        (100, 10),
        request_id="req-1",
        request_id_aliases=(),
        forward_text_by_chat_id=((200, "payload"),),
        sender_user_id=10,
        sender_username="alice",
    )
    first = store.claim((100, 10), request_id="req-1")
    assert first is not None

    now[0] += 20
    assert store.renew((100, 10), first, wait_seconds=20) is True
    now[0] += 20
    assert store.claim((100, 10), request_id="req-1") is None

    now[0] += 31
    second = store.claim((100, 10), request_id="req-1")
    assert second is not None
    assert second.owner_version == first.owner_version + 1


def test_releasing_old_claim_keeps_only_newest_duplicate_preview(tmp_path: Path) -> None:
    """A replay published during delivery must replace the old ID after failure."""

    store = PendingRequestStore(tmp_path / "requests.sqlite3", ttl_seconds=120)
    store.publish(
        (100, 10),
        request_id="req-1",
        request_id_aliases=(),
        forward_text_by_chat_id=((200, "old"),),
        sender_user_id=10,
        sender_username="alice",
    )
    claimed_old = store.claim((100, 10), request_id="req-1")
    assert claimed_old is not None
    store.publish(
        (100, 10),
        request_id="req-1",
        request_id_aliases=(),
        forward_text_by_chat_id=((200, "new"),),
        sender_user_id=10,
        sender_username="alice",
    )

    assert store.release((100, 10), claimed_old) is True
    newest = store.cancel((100, 10), request_id="req-1")
    assert newest is not None
    assert newest.forward_text_by_chat_id == ((200, "new"),)
    assert store.cancel((100, 10), request_id="req-1") is None


def test_request_log_rejects_schema_without_unique_delivery_index(tmp_path: Path) -> None:
    """The schema check must verify the uniqueness required by ON CONFLICT/idempotency."""

    storage_path = tmp_path / "requests.sqlite3"
    connection = sqlite3.connect(storage_path)
    try:
        connection.execute(
            """
            CREATE TABLE request_deliveries (
              request_id TEXT NOT NULL,
              target_chat_id INTEGER NOT NULL,
              sender_username TEXT,
              created_at TEXT NOT NULL,
              validation_status TEXT NOT NULL,
              delivery_status TEXT NOT NULL,
              last_error TEXT
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(sqlite3.DatabaseError, match="missing primary key"):
        RequestLog(storage_path)


def test_existing_delivery_database_gains_new_state_tables_without_data_loss(
    tmp_path: Path,
) -> None:
    """Upgrading a valid pre-lease database must preserve delivered rows."""

    storage_path = tmp_path / "requests.sqlite3"
    connection = sqlite3.connect(storage_path)
    try:
        connection.execute(
            """
            CREATE TABLE request_deliveries (
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
            INSERT INTO request_deliveries VALUES
              ('old-delivered', 100, 'alice', '2026-01-01T00:00:00+00:00',
               'valid', 'delivered', NULL)
            """
        )
        connection.commit()
    finally:
        connection.close()

    request_log = RequestLog(storage_path)
    assert (
        request_log.begin_delivery(
            request_id="old-delivered",
            target_chat_id=100,
            sender_username="alice",
        )
        is None
    )
    pending_store = PendingRequestStore(storage_path, ttl_seconds=120)
    published = pending_store.publish(
        (100, 10),
        request_id="new-pending",
        request_id_aliases=(),
        forward_text_by_chat_id=((200, "payload"),),
        sender_user_id=10,
        sender_username="alice",
    )
    assert published.version == 1


def test_request_log_exports_csv(tmp_path: Path) -> None:
    """Request log records should export as stable CSV."""

    request_log = RequestLog(tmp_path / "requests.sqlite3")
    lease = request_log.begin_delivery(
        request_id="req-1",
        target_chat_id=100,
        sender_username="alice",
    )
    assert lease is not None
    request_log.mark_delivery(lease=lease, status="failed", error="boom")
    records = request_log.records_since(since=date(2000, 1, 1))
    output = StringIO()

    export_records_csv(records, output)

    assert "request_id,target_chat_id,sender_username" in output.getvalue()
    assert "req-1,100,alice" in output.getvalue()
    assert "failed,boom" in output.getvalue()


def test_request_log_export_neutralizes_spreadsheet_formulas(tmp_path: Path) -> None:
    """CSV export should not emit formula-prefixed text fields directly."""

    request_log = RequestLog(tmp_path / "requests.sqlite3")
    lease = request_log.begin_delivery(
        request_id="=req-1",
        target_chat_id=100,
        sender_username="@alice",
    )
    assert lease is not None
    request_log.mark_delivery(lease=lease, status="failed", error="+boom")
    records = request_log.records_since(since=date(2000, 1, 1))
    output = StringIO()

    export_records_csv(records, output)

    assert "'=req-1,100,'@alice" in output.getvalue()
    assert "failed,'+boom" in output.getvalue()
