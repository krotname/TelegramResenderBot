"""Unit tests for SQLite request delivery storage."""

from datetime import date
from io import StringIO
from pathlib import Path

from telegram_resender.storage import RequestLog, export_records_csv


def test_request_log_tracks_delivery_idempotently(tmp_path: Path) -> None:
    """Delivered request/target pairs should not be sent again."""

    request_log = RequestLog(tmp_path / "requests.sqlite3")

    assert request_log.begin_delivery(
        request_id="req-1",
        target_chat_id=100,
        sender_username="alice",
    )
    request_log.mark_delivery(request_id="req-1", target_chat_id=100, status="delivered")

    assert not request_log.begin_delivery(
        request_id="req-1",
        target_chat_id=100,
        sender_username="alice",
    )


def test_request_log_exports_csv(tmp_path: Path) -> None:
    """Request log records should export as stable CSV."""

    request_log = RequestLog(tmp_path / "requests.sqlite3")
    request_log.begin_delivery(
        request_id="req-1",
        target_chat_id=100,
        sender_username="alice",
    )
    request_log.mark_delivery(request_id="req-1", target_chat_id=100, status="failed", error="boom")
    records = request_log.records_since(since=date(2000, 1, 1))
    output = StringIO()

    export_records_csv(records, output)

    assert "request_id,target_chat_id,sender_username" in output.getvalue()
    assert "req-1,100,alice" in output.getvalue()
    assert "failed,boom" in output.getvalue()
