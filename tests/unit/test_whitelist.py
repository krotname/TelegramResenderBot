"""Unit tests for whitelist normalization and loading."""

from pathlib import Path

import pytest

from telegram_resender.whitelist import Whitelist, normalize_username


def test_normalize_username_handles_variants() -> None:
    """Verify that whitespace, leading @ and case do not affect matching."""

    assert normalize_username("  @UserName ") == "username"
    assert normalize_username("Second") == "second"
    assert normalize_username(None) is None
    assert normalize_username("   ") is None


def test_whitelist_loads_csv_and_normalizes(tmp_path: Path) -> None:
    """Ensure first-column parsing and comment support are preserved."""

    file_path = tmp_path / "whitelist.csv"
    file_path.write_text("Alice\n@Bob\n# ignored\ncarol , extra\n", encoding="utf-8")
    whitelist = Whitelist.from_file(file_path)

    assert whitelist.contains("alice")
    assert whitelist.contains("BOB")
    assert whitelist.contains("@carol")
    assert not whitelist.contains("ignored")


def test_whitelist_missing_file_raises_error() -> None:
    """Missing whitelist file should fail early with FileNotFoundError."""

    with pytest.raises(FileNotFoundError):
        Whitelist.from_file(Path("missing.csv"))
